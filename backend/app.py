from flask import Flask, request, jsonify, send_from_directory
import os
import pandas as pd
from werkzeug.utils import secure_filename
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from flask_cors import CORS
import traceback
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow all origins

# Configurations
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
OUTPUT_FOLDER = "outputs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Number of concurrent threads
MAX_THREADS = 4

# Initialize WebDriver (One-time initialization)
def initialize_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run without UI
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

# Scraper Functions
def scrape_amazon(driver, url):
    driver.get(url)
    try:
        product_title = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "productTitle"))
        ).text.strip()
    except TimeoutException:
        product_title = "Not Available"

    try:
        mrp = driver.find_element(By.CSS_SELECTOR, "span.a-size-small.aok-offscreen").text.strip().replace('M.R.P.: ', '')
    except NoSuchElementException:
        mrp = "Not Available"

    try:
        offer_price = driver.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.strip()
    except NoSuchElementException:
        offer_price = "Not Available"

    return {'Website': 'AMAZON', 'URL': url, 'Product Name': product_title, 'MRP': mrp, 'Offer Price': offer_price}

def scrape_flipkart(driver, url):
    driver.get(url)
    try:
        product_title = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "span.B_NuCI"))
        ).text.strip()
    except TimeoutException:
        product_title = "Not Available"

    try:
        mrp = driver.find_element(By.CSS_SELECTOR, "div.yRaY8j.A6+E6v").text.strip()
    except NoSuchElementException:
        mrp = "Not Available"

    try:
        offer_price = driver.find_element(By.CSS_SELECTOR, "div.Nx9bqj.CxhGGd").text.strip()
    except NoSuchElementException:
        offer_price = "Not Available"

    return {'Website': 'FLIPKART', 'URL': url, 'Product Name': product_title, 'MRP': mrp, 'Offer Price': offer_price}

def scrape_1mg(driver, url):
    driver.get(url)
    try:
        product_title = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "h1.ProductTitle__product-title___3QMYH"))
        ).text.strip()
    except TimeoutException:
        product_title = "Not Available"

    try:
        mrp = driver.find_element(By.CSS_SELECTOR, "span.DiscountDetails__discount-price___Mdcwo").text.strip()
    except NoSuchElementException:
        mrp = "Not Available"

    try:
        offer_price = driver.find_element(By.CSS_SELECTOR, "div.PriceDetails__discount-div___nb724").text.strip()
    except NoSuchElementException:
        offer_price = "Not Available"

    return {'Website': '1MG', 'URL': url, 'Product Name': product_title, 'MRP': mrp, 'Offer Price': offer_price}

def scrape_netmeds(driver, url):
    driver.get(url)
    try:
        product_title = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.prodName h1.black-txt"))
        ).text.strip()
    except TimeoutException:
        product_title = "Not Available"

    try:
        mrp = driver.find_element(By.CSS_SELECTOR, "span.final-price span").text.strip()
    except NoSuchElementException:
        mrp = "Not Available"

    try:
        offer_price_element = driver.find_element(By.CSS_SELECTOR, "span.final-price span")
        offer_price = offer_price_element.find_element(By.XPATH, "..").text.strip().split("MRP")[1].strip()
    except NoSuchElementException:
        offer_price = "Not Available"

    return {'Website': 'NETMEDS', 'URL': url, 'Product Name': product_title, 'MRP': mrp, 'Offer Price': offer_price}

# Generic Scraper Dispatcher
def scrape_url(url):
    driver = initialize_driver()
    try:
        if 'amazon.in' in url:
            return scrape_amazon(driver, url)
        elif 'flipkart.com' in url:
            return scrape_flipkart(driver, url)
        elif '1mg.com' in url:
            return scrape_1mg(driver, url)
        elif 'netmeds.com' in url:
            return scrape_netmeds(driver, url)
        else:
            return {'Website': 'UNKNOWN', 'URL': url, 'Product Name': 'Unknown', 'MRP': 'Unknown', 'Offer Price': 'Unknown'}
    except Exception as e:
        return {'Website': 'ERROR', 'URL': url, 'Error': str(e)}
    finally:
        driver.quit()

# File Upload Endpoint
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'message': 'File uploaded successfully', 'filepath': filepath})
    return jsonify({'error': 'No file provided'}), 400

# Scraping Endpoint with Parallel Execution
@app.route('/scrape', methods=['POST'])
def scrape_urls():
    filepath = request.json.get('filepath')
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 400

    try:
        if filepath.endswith('.xlsx'):
            df = pd.read_excel(filepath, engine='openpyxl')
            urls = df.iloc[:, 0].dropna().tolist()

            if not urls:
                return jsonify({'error': 'No URLs found in the file'}), 400

            # Parallel scraping with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                results = list(executor.map(scrape_url, urls))

            output_filename = 'output.xlsx'
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            pd.DataFrame(results).to_excel(output_path, index=False)

            return jsonify({'message': 'Scraping completed', 'output_file': output_filename})

        else:
            return jsonify({'error': 'File is not an Excel (.xlsx) file'}), 400

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': f"An error occurred: {str(e)}"}), 500

# File Download Endpoint
@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    # app.run(debug=True)
    app.run(host="192.168.0.28", port=5000, debug=True)
