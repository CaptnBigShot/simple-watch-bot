import logging

from controllers import MainController


def main():
    MainController().check_watchlist_items_with_recheck()


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s: %(message)s", level=logging.INFO, datefmt="%H:%M:%S")
    main()
