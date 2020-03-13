# AllSides headlines scraper

This repository allows you to retrieve the aggregation performed by [AllSides](https://www.allsides.com/story/admin).

## Installation

```bash
virtualenv venv
source venv/bin/activate
pip install requirements.txt
```

## Running the scraper

```bash
python -m allsides_headlines
```

This will produce a `headlines.json` file in the `data` folder.
