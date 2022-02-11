"""
CLI tool to retrieve information and perform requests on packages in the DPRES
service.
"""

import itertools
import time
from pathlib import Path

import click
import humanize
import tabulate

from .client import AccessClient, get_poll_interval_iter

from .config import write_default_config


# pylint: disable=too-few-public-methods
class Context:
    """Context class for the Click application"""
    client = None


@click.group()
@click.pass_context
def cli(ctx):
    """
    DPRES Access REST API client
    """
    ctx.obj.client = AccessClient()


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


@cli.command(help="Download a preserved package from the DPRES service")
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
    client = ctx.obj.client
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
    # Infinite iterator used to provide a very simple spinner animation
    spinner_anim = itertools.cycle(["|", "|", "/", "/", "-", "-", "\\", "\\"])

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
    client = ctx.obj.client
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


@cli.command(
    help="Delete a completed DIP from the DPRES service"
)
@click.argument("dip_id")
@click.pass_context
def delete(ctx, dip_id):
    """
    Delete a completed DIP from the DPRES service.
    """
    client = ctx.obj.client

    click.echo("")
    click.echo("Proceeding to delete DIP from the service...")

    dip_deleted = client.delete_dissemination(dip_id=dip_id)

    if not dip_deleted:
        click.echo("DIP could not be deleted from the service.")

    click.echo("Done!")


@cli.group('ingest-report')
def ingest_report():
    """List and get ingest reports of a package"""
    pass


@ingest_report.command(help="List available ingest reports of a package")
@click.argument("sip_id")
@click.pass_context
def list(ctx, sip_id):
    """List available ingest reports of a package"""
    client = ctx.obj.client

    entries = client.get_ingest_report_entries(sip_id)

    headers = {
        "date": "Date",
        "status": "Status",
        "transfer_id": "Transfer ID"
    }
    output = tabulate.tabulate(entries, headers=headers)
    click.echo(output)


@ingest_report.command(help="Get an ingest report of a package")
@click.argument("sip_id")
@click.option(
    "--transfer-id", type=str,
    help=(
        "Specify the ingest report with transfer ID. "
        "Either --transfer-id or --latest flag has to be set."
    )
)
@click.option(
    "--latest", is_flag=True,
    help=(
        "Get the latest ingest report of a package. "
        "Either --latest flag or --transfer-id has to be set."
    )
)
@click.option(
    "--file-type", default="html",
    type=click.Choice(["html", "xml"]),
    help="File type of the returned ingest report. Defaults to 'html'."
)
@click.option(
    "--path", type=click.Path(dir_okay=False, writable=True), required=False,
    help=(
        "Path where the ingest report will be saved. If not "
        "specified, echo to stdout by default."
    )
)
@click.pass_context
def get(ctx, sip_id, path, transfer_id, latest, file_type):
    """Get an ingest report of a package"""
    client = ctx.obj.client

    # Validate that the ingest report is specified correctly with either
    # --latest or --transfer-id
    if not latest and not transfer_id:
        raise click.UsageError(
            "The ingest report has to be specified with either --latest flag "
            "or providing transfer ID with option --transfer-id."
        )
    if latest and transfer_id:
        raise click.UsageError(
            "Both --latest and --transfer-id provided. Specify the ingest "
            "report with only one of the options."
        )

    # Get ingest report
    if latest:
        report = client.get_latest_ingest_report(sip_id, file_type)
    else:
        report = client.get_ingest_report(sip_id, transfer_id, file_type)

    # Echo or save to given path
    if path:
        with open(path, "wb") as file:
            file.write(report)
        click.echo(f"Ingest report saved to {path}")
    else:
        click.echo(report)


def main():
    """
    Main command-line entry point
    """
    # pylint: disable=no-value-for-parameter,unexpected-keyword-arg
    cli(obj=Context())


if __name__ == "__main__":
    main()
