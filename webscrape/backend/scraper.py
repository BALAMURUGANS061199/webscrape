from flask import Flask, request, jsonify, send_from_directory
import os
import pandas as pd
from werkzeug.utils import secure_filename
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from flask_cors import CORS
import traceback
import time

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow all origins

# Configurations
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
OUTPUT_FOLDER = "outputs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Function to initialize WebDriver
def initialize_driver():
    try:
        service = Service(ChromeDriverManager().install())  # Auto-download ChromeDriver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Run in headless mode to avoid UI-related issues
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"Error initializing WebDriver: {e}")
        return None

# Scraping functions for each website

def scrape_amazon(driver, url):
    driver.get(url)
    try:
        product_title = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "productTitle"))
        ).text.strip()
    except TimeoutException:
        product_title = "Not Available"

    try:
        mrp = driver.find_element(By.CSS_SELECTOR, "span.a-size-small.aok-offscreen").text.strip().replace('M.R.P.: ', '')
    except Exception:
        mrp = "Not Available"

    try:
        offer_price = driver.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.strip()
    except Exception:
        offer_price = "Not Available"

    return {'URL': url, 'Product Name': product_title, 'MRP': mrp, 'Offer Price': offer_price}

def scrape_flipkart(driver, url):
    driver.get(url)
    try:
        product_title = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "span.B_NuCI"))
        ).text.strip()
    except TimeoutException:
        product_title = "Not Available"

    try:
        mrp = driver.find_element(By.CSS_SELECTOR, "div.yRaY8j.A6+E6v").text.strip()
    except Exception:
        mrp = "Not Available"

    try:
        offer_price = driver.find_element(By.CSS_SELECTOR, "div.Nx9bqj.CxhGGd").text.strip()
    except Exception:
        offer_price = "Not Available"

    return {'URL': url, 'Product Name': product_title, 'MRP': mrp, 'Offer Price': offer_price}

def scrape_1mg(driver, url):
    driver.get(url)
    time.sleep(2)
    try:
        # Wait for product title to be visible
        product_title = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "h1.ProductTitle__product-title___3QMYH"))
        ).text.strip()

        # Try to locate the MRP element
        try:
            mrp = driver.find_element(By.CSS_SELECTOR, "span.DiscountDetails__discount-price___Mdcwo").text.strip()
        except:
            mrp = "Not Available"
        
        # If MRP is not found, try using a more robust XPath
        if mrp == "Not Available":
            mrp = driver.find_element(By.XPATH, "//span[contains(text(), '₹')]").text.strip()

        # Extract the offer price
        offer_price = driver.find_element(By.CSS_SELECTOR, "div.PriceDetails__discount-div___nb724").text.strip()

    except Exception as e:
        print(f"Scraping error on 1mg: {e}")
        product_title, mrp, offer_price = "Not Available", "Not Available", "Not Available"
    
    return {'URL': url, 'Product Name': product_title, 'MRP': mrp, 'Offer Price': offer_price}


def scrape_netmeds(driver, url):
    driver.get(url)
    time.sleep(2)
    try:
        # Wait for product title to be visible
        product_title = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.product-name"))
        ).text.strip()

        # Extract the MRP price from the span with class "price"
        mrp_element = driver.find_element(By.CSS_SELECTOR, "span.price").text.strip()
        # The MRP is after the "MRP" label in the span, we split it out
        mrp = mrp_element.split("MRP")[1].strip() if "MRP" in mrp_element else "Not Available"

        # Extract the offer price
        offer_price = driver.find_element(By.CSS_SELECTOR, "span.final-price").text.strip()

    except Exception as e:
        print(f"Scraping error on Netmeds: {e}")
        product_title, mrp, offer_price = "Not Available", "Not Available", "Not Available"
    
    return {'URL': url, 'Product Name': product_title, 'MRP': mrp, 'Offer Price': offer_price}

def scrape_url(url):
    # Initialize WebDriver for each URL
    driver = initialize_driver()
    if driver is None:
        return {'URL': url, 'Product Name': 'Error', 'MRP': 'Error', 'Offer Price': 'Error'}
    
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
            return {'URL': url, 'Product Name': 'Unknown', 'MRP': 'Unknown', 'Offer Price': 'Unknown'}
    finally:
        driver.quit()  # Ensure the driver is closed after scraping

# File upload endpoint
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'message': 'File uploaded successfully', 'filepath': filepath})
    return jsonify({'error': 'No file provided'}), 400


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

            results = [scrape_url(url) for url in urls]

            output_filename = 'output.xlsx'
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            pd.DataFrame(results).to_excel(output_path, index=False)

            return jsonify({'message': 'Scraping completed', 'output_file': output_filename})

        else:
            return jsonify({'error': 'File is not an Excel (.xlsx) file'}), 400

    except Exception as e:
        # Log the exception details for debugging
        error_message = str(e)
        traceback_str = traceback.format_exc()
        print(f"Error in scrape_urls: {error_message}")
        print(traceback_str)
        return jsonify({'error': f"An error occurred: {error_message}"}), 500


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
