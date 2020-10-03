import click

from controllers import MainController


@click.command()
@click.option('--data_file_name', default='data.json', help='The path/name of the data file.')
def main(data_file_name):
    MainController(data_file_name).check_watchlist_items_with_recheck()


if __name__ == "__main__":
    main()
