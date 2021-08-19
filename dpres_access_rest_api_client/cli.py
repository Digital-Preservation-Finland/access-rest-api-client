"""
CLI tool for searching and downloading DIPs from the DPRES service using the
REST API.
"""

import itertools
import time
from pathlib import Path

import click
import humanize
import tabulate

from .client import AccessClient, get_poll_interval_iter


class Context:
    """Context class for the Click application"""
    client = None


@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj.client = AccessClient()


@cli.command(help="Download a preserved package from the DPRES service")
@click.option(
    "--path",
    type=click.Path(file_okay=True, dir_okay=False, writable=True),
    default=None,
    help=(
        "Path where the package will be saved. Defaults to `<aip_id>.<format>` "
        "in the working directory."
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
@click.argument("aip_id")
@click.pass_context
def download(ctx, path, archive_format, catalog, aip_id):
    """
    Download a file and save it to the given path
    """
    client = ctx.obj.client
    if not path:
        path = (Path(".").resolve() / aip_id).with_suffix(f".{archive_format}")
    else:
        path = Path(path)

    dip_request = client.create_dip_request(
        aip_id=aip_id, archive_format=archive_format,
        catalog=catalog
    )

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
            # Poll every 3 seconds
            dip_request.poll()
            poll_interval = next(poll_interval_iter)
        else:
            poll_interval -= 0.25
            time.sleep(0.25)

    click.echo("")
    click.echo(f"DIP is available, downloading to {path}...")

    # Download the DIP
    download_size, download_iter = dip_request.get_download_size_and_iter()
    human_size = humanize.naturalsize(download_size)

    with click.progressbar(
        label=f"Downloading ({human_size})...",
        length=download_size) as progressbar:
        with path.open("wb", buffering=1024*1024) as file_:
            for chunk in download_iter:
                file_.write(chunk)
                progressbar.update(1024*1024)

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
    client = ctx.obj.client
    echo_func = click.echo_via_pager if pager else click.echo

    search_results = client.search(page=page, limit=limit, query=query)
    results = []

    for entry in search_results.results:
        aip_id = entry["id"]
        pkg_type = entry["pkg_type"]
        createdate = entry["createdate"]
        lastmoddate = "N/A"

        if "lastmoddate" in entry:
            lastmoddate = entry["lastmoddate"]

        results.append((aip_id, pkg_type, createdate, lastmoddate))

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


def main():
    cli(obj=Context())


if __name__ == "__main__":
    main()
