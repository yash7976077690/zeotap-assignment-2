import os
import requests
from bs4 import BeautifulSoup
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser
from flask import Flask, request, render_template
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Download NLTK data
nltk.download('punkt')
nltk.download('stopwords')

# Initialize Flask app
app = Flask(__name__)

# Define schema for Whoosh index
schema = Schema(
    title=TEXT(stored=True),
    content=TEXT(stored=True),
    cdp_name=ID(stored=True)
)

# Create or open the index directory
if not os.path.exists("indexdir"):
    os.mkdir("indexdir")
    ix = create_in("indexdir", schema)
else:
    ix = open_dir("indexdir")

# List of CDP documentation URLs
cdp_docs = {
    "Segment": "https://segment.com/docs/?ref=nav",
    "mParticle": "https://docs.mparticle.com/",
    "Lytics": "https://docs.lytics.com/",
    "Zeotap": "https://docs.zeotap.com/home/en-us/"
}

# Preprocess text
def preprocess_text(text):
    stop_words = set(stopwords.words('english'))
    tokens = word_tokenize(text.lower())
    return " ".join([word for word in tokens if word.isalnum() and word not in stop_words])

# Scrape documentation
def scrape_documentation(url, cdp_name):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    sections = soup.find_all(['h1', 'h2', 'h3', 'p'])  # Adjust based on the structure of the docs
    data = []
    current_title = ""
    current_content = ""

    for section in sections:
        if section.name in ['h1', 'h2', 'h3']:
            if current_title and current_content:
                data.append({
                    'title': current_title,
                    'content': preprocess_text(current_content),
                    'cdp_name': cdp_name
                })
            current_title = section.get_text()
            current_content = ""
        elif section.name == 'p':
            current_content += section.get_text() + " "

    if current_title and current_content:
        data.append({
            'title': current_title,
            'content': preprocess_text(current_content),
            'cdp_name': cdp_name
        })

    return data

# Index documentation
def index_documentation():
    writer = ix.writer()
    for cdp_name, url in cdp_docs.items():
        print(f"Scraping {cdp_name} documentation...")
        docs = scrape_documentation(url, cdp_name)
        for doc in docs:
            writer.add_document(
                title=doc['title'],
                content=doc['content'],
                cdp_name=doc['cdp_name']
            )
    writer.commit()
    print("Documentation indexed successfully.")

# Search the index
def search_index(query, cdp_name):
    with ix.searcher() as searcher:
        query_parser = QueryParser("content", ix.schema)
        query = query_parser.parse(query)
        results = searcher.search(query, limit=5)
        return [hit['content'] for hit in results]

# Generate response
def generate_response(query, cdp_name):
    results = search_index(query, cdp_name)
    if results:
        return results[0]  # Return the most relevant result
    else:
        return "Sorry, I couldn't find any relevant information."

# Flask routes
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        query = request.form['query']
        cdp_name = request.form['cdp_name']
        response = generate_response(query, cdp_name)
        return render_template('index.html', response=response, cdp_name=cdp_name)
    return render_template('index.html', response=None, cdp_name=None)

# Run the app
if __name__ == '__main__':
    # Index documentation on first run
    if not os.listdir("indexdir"):
        index_documentation()
    app.run(debug=True)