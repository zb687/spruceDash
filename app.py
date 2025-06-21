# app.py
import os
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_caching import Cache
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from eci_api_service import ECIApiService
from analytics_service import AnalyticsService
from database_service import DatabaseService

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure caching
cache = Cache(app, config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': os.getenv('REDIS_URL', 'redis://localhost:6379')
})

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
eci_service = ECIApiService(
    endpoint=os.getenv('ECI_API_ENDPOINT'),
    api_key=os.getenv('ECI_API_KEY')
)
analytics_service = AnalyticsService()
db_service = DatabaseService(os.getenv('DATABASE_URL'))

# Initialize scheduler for background data collection
scheduler = BackgroundScheduler()
scheduler.start()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/dashboard/summary')
@cache.cached(timeout=300)  # Cache for 5 minutes
def dashboard_summary():
    try:
        # Get date range for today
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # Fetch data
        sales_data = eci_service.get_daily_sales(yesterday, today)
        inventory_alerts = eci_service.get_inventory_alerts()
        
        summary = {
            'today_sales': analytics_service.calculate_daily_sales(sales_data),
            'inventory_alerts': len(inventory_alerts),
            'top_selling_items': analytics_service.get_top_items(sales_data, limit=5),
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error in dashboard summary: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/alerts')
@cache.cached(timeout=300)
def inventory_alerts():
    try:
        alerts = eci_service.get_inventory_alerts()
        return jsonify(alerts)
    except Exception as e:
        logger.error(f"Error getting inventory alerts: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales/by-customer')
def sales_by_customer():
    try:
        account_number = request.args.get('account_number')
        days = int(request.args.get('days', 30))
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        sales_data = eci_service.get_customer_sales(
            account_number, start_date, end_date
        )
        
        return jsonify(sales_data)
    except Exception as e:
        logger.error(f"Error getting customer sales: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales/by-brand')
@cache.cached(timeout=3600)  # Cache for 1 hour
def sales_by_brand():
    try:
        days = int(request.args.get('days', 30))
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        brand_sales = analytics_service.get_sales_by_brand(start_date, end_date)
        
        return jsonify(brand_sales)
    except Exception as e:
        logger.error(f"Error getting brand sales: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/demand/forecast/<item_number>')
def demand_forecast(item_number):
    try:
        forecast_data = analytics_service.calculate_demand_forecast(item_number)
        return jsonify(forecast_data)
    except Exception as e:
        logger.error(f"Error calculating demand forecast: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/daily')
def daily_report():
    try:
        report_date = request.args.get('date', datetime.now().date().isoformat())
        report_data = analytics_service.generate_daily_report(report_date)
        
        return jsonify(report_data)
    except Exception as e:
        logger.error(f"Error generating daily report: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Background jobs
def collect_daily_data():
    """Scheduled job to collect and store daily data"""
    try:
        logger.info("Starting daily data collection...")
        
        # Collect yesterday's data
        yesterday = datetime.now().date() - timedelta(days=1)
        
        # Get sales data
        sales_data = eci_service.get_daily_sales(yesterday, yesterday)
        db_service.store_sales_data(sales_data)
        
        # Update inventory levels
        inventory_data = eci_service.get_all_inventory()
        db_service.update_inventory_levels(inventory_data)
        
        logger.info("Daily data collection completed")
    except Exception as e:
        logger.error(f"Error in daily data collection: {str(e)}")

# Schedule daily data collection at 2 AM
scheduler.add_job(
    collect_daily_data,
    'cron',
    hour=2,
    minute=0,
    id='daily_data_collection'
)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_ENV') == 'development')
