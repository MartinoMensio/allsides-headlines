# AllSides headlines scraper

This repository allows you to retrieve the aggregation performed by [AllSides](https://www.allsides.com/story/admin).

## Installation

```bash
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the scraper

```bash
python -m allsides_headlines
```

This will produce a `headlines.json` file in the `data` folder.


Errors in the data:

Duplicates
```python
from narrative_comparison import allsides, utils

allsides_headlines = allsides.get_headlines()
urls = []
for i, h in enumerate(allsides_headlines):
    for a in h['articles']:
        urls_cluster_id.append(i)
        urls_cluster_topic_id.append(topics.index(h['Topics']))
        url = a['url']
        urls.append(url)
# https://stackoverflow.com/questions/45252243/finding-the-first-duplicate-element-in-an-ordered-list
duplicates = [n for i , n in enumerate(urls) if n in urls[i+1:] and n not in urls[:i]]

for d in duplicates:
    headlines_matching = [h for h in allsides_headlines if any(a for a in h['articles'] if a['url'] == d)]
    headlines_urls = []
    for headline_matching in headlines_matching:
        headline_url = headline_matching['url']
        headlines_urls.append(headline_url)
    if len(headlines_urls) > 1:
        # print('multiple', ' '.join(headlines_urls))
        print('')
    else:
        # print(headlines_urls[0])
        headline_matching = headlines_matching[0]
        articles_matching = 



```




Scraping not working on:

- post-gazette.com: empty text
- npr.org: cookie sentence