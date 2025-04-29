"""
CLI tool to retrieve information and perform requests on packages in the DPRES
service.
"""

import itertools
import time
from pathlib import Path
import os

import click
import humanize
import tabulate
from click.exceptions import ClickException
from requests.exceptions import HTTPError

from .v2.client import AccessClient
from .base import get_poll_interval_iter
from .v3.client import AccessClient as ClientV3

from .config import write_default_config


# pylint: disable=too-few-public-methods
class Context:
    """Context class for the Click application"""
    client_v2 = None
    client_v3 = None


def _spinner_animation():
    """Provide an interable spinner animation.

    :return: Infinite iterator used to provide a very simple spinner animation.
    """
    return itertools.cycle(["|", "|", "/", "/", "-", "-", "\\", "\\"])


@click.group()
@click.pass_context
def cli(ctx):
    """
    DPRES Access REST API client
    """
    ctx.obj.client_v2 = AccessClient()
    ctx.obj.client_v3 = ClientV3()


@cli.command(
    # Define command name for backwards compatibility with Click 6 and older
    "write-config",
    help="Write default configuration file"
)
def write_config():
    """
    Write default configuration file to user's home directory if it doesn't
    exist
    """
    path = write_default_config()

    if path:
        click.echo(f"Configuration file written to {path}")
    else:
        click.echo("Configuration file already exists")


@cli.group()
def dip():
    """Download and delete DIPs created from a package"""
    pass


@dip.command(help="Download a preserved package from the DPRES service")
@click.option(
    "--path",
    type=click.Path(file_okay=True, dir_okay=False, writable=True),
    default=None,
    help=(
        "Path where the package will be saved. Defaults to "
        "`<aip_id>.<format>` in the working directory."
    )
)
@click.option(
    "--archive-format",
    type=click.Choice(["zip", "tar"]),
    default="zip",
    help="Archive type to download. Defaults to 'zip'."
)
@click.option(
    "--catalog",
    type=str,
    default=None,
    help=(
        "Optional schema catalog to use for the generated archive. "
        "Defaults to the newest available catalog."
    )
)
@click.option(
    "--delete/--no-delete",
    default=True,
    help=(
        "Delete the DIP from the DPRES service after it has been downloaded. "
        "Defaults to True."
    )
)
@click.argument("aip_id")
@click.pass_context
def download(ctx, path, archive_format, catalog, delete, aip_id):
    """
    Download a file and save it to the given path
    """
    client = ctx.obj.client_v2
    if not path:
        path = (Path(".").resolve() / aip_id).with_suffix(f".{archive_format}")
    else:
        path = Path(path)

    # TODO: We could cache the DIP creation request with a reasonable
    # time-to-live (eg. one day?)
    #
    # This means that if the user runs this command with certain parameters,
    # starts polling for the DIP but closes the application before the download
    # is finished, the previous polling URL will be used on next launch
    # if the exact same parameters are used.
    # This prevents the creation of new redundant DIP on the server-side.

    dip_request = client.create_dip_request(
        aip_id=aip_id, archive_format=archive_format,
        catalog=catalog
    )

    # Start polling until the disseminated DIP is ready for download
    _download_poll_until_ready(dip_request)

    click.echo("")
    click.echo(f"DIP is available, downloading to {path}...")

    _download_save_to_path(dip_request, path)

    if delete:
        click.echo("Proceeding to delete DIP from the service...")

        dip_request.delete()

    click.echo("Done!")


def _download_poll_until_ready(dip_request):
    """
    Poll for DIP until it is ready for download. Display a spinner animation
    while the user is waiting.
    """
    spinner_anim = _spinner_animation()

    # Start polling until the disseminated DIP is ready for download
    poll_interval = -0.1
    poll_interval_iter = get_poll_interval_iter()
    while not dip_request.ready:
        # Print a status message with a simple spinner animation so that the
        # user doesn't get antsy
        click.echo(
            f"DIP has been scheduled for creation, polling until the DIP is "
            f"ready for download... {next(spinner_anim)}"
            # Carriage return so that the same line is overwritten
            f"\r",
            nl=False
        )

        if poll_interval < 0:
            # Poll with start interval of 3s and max of 60s
            dip_request.check_status()
            poll_interval = next(poll_interval_iter)
        else:
            poll_interval -= 0.25
            time.sleep(0.25)


def _download_save_to_path(dip_request, path):
    """
    Download the DIP to the given path.
    Display a progress bar during the download.
    """
    # Download the DIP
    download_size = dip_request.download_size
    human_size = humanize.naturalsize(download_size)

    with click.progressbar(
        label=f"Downloading ({human_size})...",
        length=download_size) as progressbar:
        with path.open("wb", buffering=1024 * 1024) as file_:
            for chunk in dip_request.download_iter:
                file_.write(chunk)
                progressbar.update(1024 * 1024)


@dip.command(
    help="Delete a completed DIP from the DPRES service"
)
@click.argument("dip_id")
@click.pass_context
def delete(ctx, dip_id):
    """
    Delete a completed DIP from the DPRES service.
    """
    client = ctx.obj.client_v2

    click.echo("")
    click.echo("Proceeding to delete DIP from the service...")

    dip_deleted = client.delete_dissemination(dip_id=dip_id)

    if not dip_deleted:
        click.echo("DIP could not be deleted from the service.")

    click.echo("Done!")


@cli.command(
    help="List and search for preserved packages in the DPRES service"
)
@click.option(
    "--page", default=1, type=int,
    help=(
        "Page to retrieve. `--limit` determines the amount of entries per "
        "page."
    )
)
@click.option(
    "--limit", default=1000, type=int,
    help="Maximum amount of results to retrieve per page"
)
@click.option(
    "--query", default="pkg_type:AIP", type=str,
    help=(
        "Optional search query. If not provided, only downloadable packages "
        "(AIPs) will be returned.\n\n"
        "Queries use the Solr version of the Lucene "
        "search syntax. See the DPRES API documentation for details."
    )
)
@click.option(
    "--pager/--no-pager", default=True,
    help=(
        "Enable interactive pager to allow scrolling in the results. "
        "Pager is always disabled when in a non-interactive environment."
    )
)
@click.pass_context
def search(ctx, page, limit, query, pager):
    """
    List and search for packages in the DPRES service
    """
    client = ctx.obj.client_v2
    echo_func = click.echo_via_pager if pager else click.echo

    search_results = client.search(page=page, limit=limit, query=query)
    results = []

    for entry in search_results.results:
        lastmoddate = "N/A"

        if "lastmoddate" in entry:
            lastmoddate = entry["lastmoddate"]

        results.append(
            (entry["id"], entry["pkg_type"], entry["createdate"], lastmoddate)
        )

    tabulated = tabulate.tabulate(
        results,
        headers=("ID", "Type", "Creation date", "Modification date")
    )

    # 'next' URL is provided if more results are available.
    more_results_available = bool(search_results.next_url)

    output = "".join([
        f"Displaying page {page} with {len(results)} results. ",
        "More page(s) are available." if more_results_available else "",
        "\n\n",
        tabulated
    ])
    echo_func(output)


@cli.command(help="Upload package to DPRES Service")
@click.argument(
    "file_path", type=click.Path(exists=True, file_okay=True, readable=True)
)
@click.option(
    "--chunk-size",
    type=int,
    default=8192,
    help=(
        "How big of a chunk size each part will be when uploading "
        "to DPRES Service"
    ),
)
@click.option(
    "--enable-resumable",
    type=bool,
    is_flag=True,
    default=False,
    help="Enable resumable",
)
@click.pass_context
def upload(ctx, chunk_size, enable_resumable, file_path):
    """Upload given file.

    If the file is empty or it isn't a proper archive, raise an error since
    that kind of files are not valid and there is no sense to upload them.
    """
    if os.stat(str(file_path)).st_size == 0:
        raise ClickException("Given file is empty.")
    if not _has_valid_file_suffix(str(file_path)):
        raise ClickException("File format not supported. The upload must be a "
                             ".zip, .tar, .tar.gz, or .tar.bz2 file.")
    cache_file = None
    if enable_resumable:
        try:
            cache_file_path = (
                Path.home() / ".cache" / "dpres_access_rest_api_client"
            )
            cache_file_path.mkdir(parents=True, exist_ok=True)
        except PermissionError as err:
            raise ClickException(
                "Resumable option requires permission to write to "
                f"[{err.filename}]"
            )
        cache_file = str(cache_file_path / "tus_storage")
    uploader = ctx.obj.client_v3.create_uploader(
        file_path=str(file_path),
        chunk_size=chunk_size,
        store_url=enable_resumable,
        cache_file=cache_file,
    )
    upload_length = uploader.get_file_size()
    current_offset = uploader.offset
    with click.progressbar(length=upload_length,
                           label="Uploading to DPRES") as bar:
        while uploader.offset < upload_length:
            uploader.upload_chunk()
            # progressbar updates in "steps" so we need to provide the
            # difference between new offset and previous offset so that
            # the bar displays correctly.
            bar.update(abs(uploader.offset - current_offset))
            current_offset = uploader.offset
    transfer_id = uploader.url.split("/")[-1]
    click.echo(
        f"Package uploaded successfully! Your transfer ID is {transfer_id}")


def _has_valid_file_suffix(filename):
    """Check that the uploaded file has a valid file ending.

    The preservation service only accepts .zip, .tar, .tar.gz or .tar.bz2
    files, so if the uploaded file doesn't have the correct file ending, it
    will be rejected.
    """
    if filename.endswith(".zip"):
        return True
    if filename.endswith(".tar"):
        return True
    if filename.endswith(".tar.gz"):
        return True
    if filename.endswith(".tar.bz2"):
        return True
    return False


@cli.group("transfer")
def transfer():
    """List transfers related commands"""
    pass


@transfer.command("info", help="Display information on given transfer")
@click.argument("transfer_id")
@click.pass_context
def get_transfer_info(ctx, transfer_id):
    """Get the transfer and display the information"""
    client = ctx.obj.client_v3
    try:
        data = client.get_transfer(transfer_id=transfer_id)
    except HTTPError:
        raise ClickException(f"No transfer found for '{transfer_id}'")

    click.echo(f'Transfer ID: {data["transfer_id"]}')
    if data["sip"]:
        click.echo(f'SIP ID: {data["sip"]["sip_id"]}')
    click.echo(f'Filename: {data["filename"]}')
    click.echo(f'Status: {data["status"]}')
    click.echo(f'Timestamp: {data["timestamp"]}')


# TODO: Provide "auto" file-type as choice option so that it'd make
#       the selection based on given "path" output.
@transfer.command(
    "get-report",
    help=(
        "Download report for given transfer. "
        "If the transfer hasn't been processed yet, poll it until it has been."
    ),
)
@click.argument("transfer_id")
@click.option(
    "--file-type",
    default="xml",
    type=click.Choice(["html", "xml"]),
    help="File type of the returned validation report. Defaults to 'xml'.",
)
@click.option(
    "--path",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help=(
        "Path where the validation report will be saved to. "
        "Defaults to `<transfer-id>-report.<file-type>` in the working "
        "directory."
    ),
)
@click.pass_context
def get_transfer_report(ctx, transfer_id, file_type, path):
    """Poll and download given transfer's validation report"""
    client = ctx.obj.client_v3
    _poll_until_transfer_processed(
        client=client, transfer_id=transfer_id
    )

    click.echo("Downloading SIP validation report...")
    report = client.get_validation_report(
        transfer_id=transfer_id, report_type=file_type
    )

    if not path:
        path = Path(".").resolve() / f"{transfer_id}-report.{file_type}"
    else:
        path = Path(path)

    with open(path, "wb") as file:
        file.write(report)
    click.echo(f"Validation report saved to {path}.")


def _poll_until_transfer_processed(client, transfer_id):
    """Shorthand function to keep polling until expected transfer has the
    expected status to continue with.

    :param client: The client to conduct the request with.
    :param transfer_id: The transfer ID to poll for.
    :return: Status of the processed transfer in string.
    """
    spinner_anim = _spinner_animation()
    processed_statuses = ["accepted", "rejected"]
    poll_interval = -0.1
    poll_interval_iter = get_poll_interval_iter()

    # See if the transfer has already been processed, in which case we don't
    # need to poll it at all.
    try:
        data = client.get_transfer(transfer_id=transfer_id)
        current_status = data["status"]
    except HTTPError:
        click.echo("")
        raise ClickException(f"No transfer found for '{transfer_id}'")

    while current_status not in processed_statuses:
        # Print a status message with a simple spinner animation so that the
        # user doesn't get antsy
        click.echo(
            f'The SIP has the status "{current_status}". '
            "Polling the DPS ingest for the SIP validation report..."
            f"{next(spinner_anim)}"
            # Carriage return so that the same line is overwritten
            f"\r",
            nl=False,
        )

        if poll_interval < 0:
            # Poll with start interval of 3s and max of 60s
            data = client.get_transfer(transfer_id=transfer_id)
            current_status = data["status"]
            poll_interval = next(poll_interval_iter)

        poll_interval -= 0.25
        time.sleep(0.25)

    click.echo("Polling is done. Transfer has been processed.")
    click.echo(f"Transfer has the status of '{current_status}'")


@transfer.command(
    "delete", help="Delete transfer information and its report"
)
@click.argument("transfer_id")
@click.pass_context
def delete_transfer(ctx, transfer_id):
    """Delete the transfer and its report permanently."""
    client = ctx.obj.client_v3
    is_success = client.delete_transfer(transfer_id=transfer_id)
    if is_success:
        click.echo(f"Transfer ID '{transfer_id}' has been deleted.")
    else:
        raise ClickException(f"No transfer found for '{transfer_id}'.")


@transfer.command("list", help="List recent transfers")
@click.option(
    "--status",
    default=None,
    type=click.Choice(
        ["None", "accepted", "in_progress", "rejected", "uploading"]
    ),
    help=(
        "Optional status filter. If not provided, all transfers are returned."
    ),
)
@click.option(
    "--page",
    default=1,
    type=int,
    help=(
        "Page to retrieve. `--limit` determines the amount of entries per "
        "page."
    ),
)
@click.option(
    "--limit",
    default=1000,
    type=int,
    help="Maximum amount of results to retrieve per page",
)
@click.option(
    "--pager/--no-pager",
    default=True,
    help=(
        "Enable interactive pager to allow scrolling in the results. "
        "Pager is always disabled when in a non-interactive environment."
    ),
)
@click.pass_context
def list_transfers(ctx, status, page, limit, pager):
    """Get list of transfers and display their information."""
    client = ctx.obj.client_v3
    echo_func = click.echo_via_pager if pager else click.echo
    try:
        search_results = client.list_transfers(
            status=status,
            page=page,
            limit=limit,
        )
    except HTTPError as err:
        raise ClickException(_extract_http_error_message(err=err))

    results = []

    for entry in search_results.results:
        sip_id = "-"

        if entry["sip"]:
            sip_id = entry["sip"]["sip_id"]

        results.append(
            (
                entry["transfer_id"],
                sip_id,
                entry["filename"],
                entry["status"],
                entry["timestamp"],
            )
        )

    tabulated = tabulate.tabulate(
        results,
        headers=("Transfer ID", "SIP ID", "Filename", "Status", "Timestamp"),
    )

    # 'next' URL is provided if more results are available.
    more_results_available = bool(search_results.next_url)

    output = "".join(
        [
            f"Displaying page {page} with {len(results)} results. ",
            "More page(s) are available." if more_results_available else "",
            "\n\n",
            tabulated,
        ]
    )
    echo_func(output)


def _extract_http_error_message(err: HTTPError) -> str:
    """Function to attempt to extract the error response message.
    If somehow unable to, will return the default error message
    generated by HTTPError.

    :param err: HTTPError exception class.
    :return: Error message that would be displayed.
    """
    try:
        data = err.response.json()["data"]
    except (KeyError, ValueError):
        # Catching ValueError if the response text was not json.
        return str(err)
    message = '\n'.join(f"- {x}: {y}" for x, y in data.items())
    return f"Server responded with following message:\n{message}"


def main():
    """
    Main command-line entry point
    """
    # pylint: disable=no-value-for-parameter,unexpected-keyword-arg
    cli(obj=Context())


if __name__ == "__main__":
    main()
