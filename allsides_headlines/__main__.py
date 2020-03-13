import typer

from . import scraper

def main():
    typer.run(scraper.scrape)

if __name__ == "__main__":
    main()