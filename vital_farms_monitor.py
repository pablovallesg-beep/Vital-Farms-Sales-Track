#!/usr/bin/env python3
"""
Vital Farms Stock Monitoring Script
Monitors Instacart availability across 10 key ZIP codes
Completely free and automated via GitHub Actions
"""

import json
import csv
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
import time

# Your 10 critical ZIP codes
ZIP_CODES = {
    "94301": "Palo Alto, CA",
    "90210": "Beverly Hills, CA",
    "94024": "Los Altos, CA",
    "10019": "Manhattan, NYC",
    "10583": "Scarsdale, NY",
    "78746": "Austin, TX",
    "77005": "Houston, TX",
    "02138": "Cambridge, MA",
    "20816": "Bethesda, MD",
    "98112": "Seattle, WA"
}

SEARCH_TERM = "Vital Farms eggs"
OUTPUT_CSV = "vital_farms_data.csv"
OUTPUT_JSON = "vital_farms_data.json"


def check_instacart_availability(zip_code, area_name, headless=True):
    """
    Check Vital Farms availability on Instacart for a specific ZIP code
    
    Args:
        zip_code: ZIP code to check
        area_name: Human-readable area name
        headless: Run browser in headless mode
        
    Returns:
        dict with availability data
    """
    print(f"\n{'='*60}")
    print(f"Checking ZIP: {zip_code} ({area_name})")
    print(f"{'='*60}")
    
    results = []
    
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        try:
            # Go to Instacart
            print(f"Loading Instacart...")
            page.goto("https://www.instacart.com/", timeout=30000)
            time.sleep(3)
            
            # Set ZIP code
            print(f"Setting ZIP code to {zip_code}...")
            try:
                # Look for ZIP code input or location selector
                # Note: Instacart's UI changes frequently, so we have multiple selectors
                
                # Try to find and click location button
                location_selectors = [
                    'button[aria-label*="location"]',
                    'button:has-text("Enter your address")',
                    '[data-testid="location-selector"]',
                    'input[placeholder*="address"]',
                    'input[placeholder*="ZIP"]'
                ]
                
                clicked = False
                for selector in location_selectors:
                    try:
                        page.click(selector, timeout=5000)
                        clicked = True
                        break
                    except:
                        continue
                
                if clicked:
                    time.sleep(2)
                    # Type ZIP code
                    page.keyboard.type(zip_code)
                    time.sleep(1)
                    page.keyboard.press('Enter')
                    time.sleep(3)
                else:
                    print("Warning: Could not find location selector, attempting direct navigation...")
                    # Try direct URL with ZIP code
                    page.goto(f"https://www.instacart.com/store?zip_code={zip_code}", timeout=30000)
                    time.sleep(3)
                    
            except Exception as e:
                print(f"Error setting ZIP code: {e}")
                print("Attempting to continue anyway...")
            
            # Search for Vital Farms
            print(f"Searching for '{SEARCH_TERM}'...")
            try:
                search_selectors = [
                    'input[placeholder*="Search"]',
                    'input[type="search"]',
                    'input[aria-label*="Search"]',
                    '[data-testid="search-input"]'
                ]
                
                searched = False
                for selector in search_selectors:
                    try:
                        page.fill(selector, SEARCH_TERM, timeout=5000)
                        page.keyboard.press('Enter')
                        searched = True
                        break
                    except:
                        continue
                
                if not searched:
                    print("Warning: Could not find search box")
                    # Try direct search URL
                    search_query = SEARCH_TERM.replace(' ', '+')
                    page.goto(f"https://www.instacart.com/store/search?query={search_query}&zip_code={zip_code}", timeout=30000)
                
                time.sleep(5)  # Wait for results to load
                
            except Exception as e:
                print(f"Error searching: {e}")
                browser.close()
                return results
            
            # Extract product information
            print("Extracting product data...")
            
            # Take a screenshot for debugging
            page.screenshot(path=f"screenshot_{zip_code}.png")
            
            # Try to find product cards
            # Note: Selectors may need adjustment based on Instacart's current HTML structure
            try:
                # Wait for products to appear
                page.wait_for_selector('[data-testid="product-card"], .product-card, [class*="ProductCard"]', timeout=10000)
                
                # Get all product elements
                products = page.query_selector_all('[data-testid="product-card"], .product-card, [class*="ProductCard"]')
                
                print(f"Found {len(products)} products on page")
                
                for idx, product in enumerate(products[:10]):  # Check first 10 results
                    try:
                        # Extract product name
                        product_name = product.inner_text()
                        
                        # Only process if it's actually Vital Farms
                        if "vital farms" in product_name.lower():
                            # Try to extract price
                            price = "N/A"
                            try:
                                price_elem = product.query_selector('[data-testid="price"], .price, [class*="price"]')
                                if price_elem:
                                    price = price_elem.inner_text().strip()
                            except:
                                pass
                            
                            # Try to determine availability
                            availability = "Unknown"
                            try:
                                # Look for out of stock indicators
                                product_html = product.inner_html().lower()
                                if "out of stock" in product_html or "unavailable" in product_html:
                                    availability = "Out of Stock"
                                elif "add to cart" in product_html or "add" in product_html:
                                    availability = "In Stock"
                                else:
                                    availability = "Available"
                            except:
                                pass
                            
                            # Try to get store info
                            store = "Multiple Stores"
                            try:
                                store_elem = product.query_selector('[data-testid="store-name"], .store-name')
                                if store_elem:
                                    store = store_elem.inner_text().strip()
                            except:
                                pass
                            
                            result = {
                                "timestamp": datetime.now().isoformat(),
                                "zip_code": zip_code,
                                "area": area_name,
                                "product": product_name.split('\n')[0],  # First line usually has product name
                                "price": price,
                                "availability": availability,
                                "store": store
                            }
                            
                            results.append(result)
                            print(f"  ✓ Found: {result['product']} - {result['availability']} - {result['price']}")
                            
                    except Exception as e:
                        print(f"  Error processing product {idx}: {e}")
                        continue
                
                if not results:
                    print("  ⚠️  No Vital Farms products found in results")
                    # Add a "not found" entry
                    results.append({
                        "timestamp": datetime.now().isoformat(),
                        "zip_code": zip_code,
                        "area": area_name,
                        "product": "Vital Farms (not found in search)",
                        "price": "N/A",
                        "availability": "Not Found",
                        "store": "N/A"
                    })
                
            except Exception as e:
                print(f"Error extracting products: {e}")
                print("Page may have loaded differently than expected")
                # Add error entry
                results.append({
                    "timestamp": datetime.now().isoformat(),
                    "zip_code": zip_code,
                    "area": area_name,
                    "product": "Error",
                    "price": "N/A",
                    "availability": f"Scraping Error: {str(e)[:50]}",
                    "store": "N/A"
                })
                
        except Exception as e:
            print(f"Critical error for {zip_code}: {e}")
            results.append({
                "timestamp": datetime.now().isoformat(),
                "zip_code": zip_code,
                "area": area_name,
                "product": "Critical Error",
                "price": "N/A",
                "availability": f"Error: {str(e)[:50]}",
                "store": "N/A"
            })
            
        finally:
            browser.close()
    
    return results


def save_results(all_results):
    """Save results to CSV and JSON files"""
    
    # Save to CSV
    if all_results:
        print(f"\nSaving results to {OUTPUT_CSV}...")
        
        # Check if file exists to determine if we need headers
        file_exists = os.path.exists(OUTPUT_CSV)
        
        with open(OUTPUT_CSV, 'a', newline='', encoding='utf-8') as f:
            fieldnames = ['timestamp', 'zip_code', 'area', 'product', 'price', 'availability', 'store']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            for result in all_results:
                writer.writerow(result)
        
        print(f"✓ Saved {len(all_results)} records to CSV")
        
        # Also save to JSON for easy reading
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2)
        
        print(f"✓ Saved to JSON")
    else:
        print("No results to save")


def print_summary(all_results):
    """Print a summary of findings"""
    
    print("\n" + "="*60)
    print("SUMMARY REPORT")
    print("="*60)
    
    if not all_results:
        print("No data collected")
        return
    
    # Count by availability status
    in_stock = sum(1 for r in all_results if "in stock" in r['availability'].lower() or "available" in r['availability'].lower())
    out_of_stock = sum(1 for r in all_results if "out of stock" in r['availability'].lower())
    not_found = sum(1 for r in all_results if "not found" in r['availability'].lower())
    errors = sum(1 for r in all_results if "error" in r['availability'].lower())
    
    print(f"\nTotal Checks: {len(all_results)}")
    print(f"✓ In Stock: {in_stock}")
    print(f"✗ Out of Stock: {out_of_stock}")
    print(f"? Not Found: {not_found}")
    print(f"⚠ Errors: {errors}")
    
    # Show details by ZIP
    print("\nDetails by ZIP Code:")
    print("-" * 60)
    for zip_code, area_name in ZIP_CODES.items():
        zip_results = [r for r in all_results if r['zip_code'] == zip_code]
        if zip_results:
            status = zip_results[0]['availability']
            price = zip_results[0]['price']
            print(f"{zip_code} ({area_name:20s}): {status:15s} - {price}")
        else:
            print(f"{zip_code} ({area_name:20s}): No data")
    
    print("\n" + "="*60)


def main():
    """Main execution function"""
    
    print("\n" + "="*60)
    print("VITAL FARMS MONITORING SYSTEM")
    print("="*60)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Checking {len(ZIP_CODES)} ZIP codes")
    print("="*60)
    
    all_results = []
    
    # Check each ZIP code
    for zip_code, area_name in ZIP_CODES.items():
        try:
            results = check_instacart_availability(zip_code, area_name)
            all_results.extend(results)
            
            # Be nice to the website - wait between requests
            print(f"Waiting 10 seconds before next ZIP...")
            time.sleep(10)
            
        except Exception as e:
            print(f"Failed to check {zip_code}: {e}")
            continue
    
    # Save results
    save_results(all_results)
    
    # Print summary
    print_summary(all_results)
    
    print(f"\nEnd Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    return all_results


if __name__ == "__main__":
    main()
