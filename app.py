# app.py
import os
import sys

# Fix Python path for Railway
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_caching import Cache
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
from apscheduler.schedulers.background import BackgroundScheduler

# Import services
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
@cache.cached(timeout=300, query_string=True)
def dashboard_summary():
    try:
        # Get date parameters or default to last 7 days
        end_date = request.args.get('end_date')
        start_date = request.args.get('start_date')
        
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = datetime.now().date()
            
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = end_date - timedelta(days=7)
        
        # Fetch data for the date range
        sales_data = eci_service.get_daily_sales(start_date, end_date)
        inventory_alerts = eci_service.get_inventory_alerts()
        
        summary = {
            'today_sales': analytics_service.calculate_daily_sales(sales_data),
            'inventory_alerts': len(inventory_alerts),
            'top_selling_items': analytics_service.get_top_items(sales_data, limit=5),
            'last_updated': datetime.now().isoformat(),
            'period_label': f'{start_date} to {end_date}'
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
@cache.cached(timeout=3600)
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

@app.route('/api/sales/trend')
def sales_trend():
    try:
        end_date = request.args.get('end_date')
        start_date = request.args.get('start_date')
        
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = datetime.now().date()
            
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = end_date - timedelta(days=30)
        
        # Get daily sales totals
        sales_data = eci_service.get_daily_sales(start_date, end_date)
        
        # Aggregate by date
        daily_totals = {}
        for sale in sales_data:
            date_str = sale['invoice_date'].strftime('%Y-%m-%d')
            if date_str not in daily_totals:
                daily_totals[date_str] = 0
            daily_totals[date_str] += sale['extended_price']
        
        # Fill missing dates with 0
        dates = []
        sales = []
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            dates.append(date_str)
            sales.append(daily_totals.get(date_str, 0))
            current_date += timedelta(days=1)
        
        return jsonify({
            'dates': dates,
            'sales': sales
        })
    except Exception as e:
        logger.error(f"Error getting sales trend: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/data-availability')
def check_data_availability():
    try:
        # Check last 365 days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)
        
        # Get all sales in the period
        sales_data = eci_service.get_daily_sales(start_date, end_date)
        
        if sales_data:
            # Group by date
            dates = {}
            for sale in sales_data:
                date_str = sale['invoice_date'].strftime('%Y-%m-%d')
                if date_str not in dates:
                    dates[date_str] = 0
                dates[date_str] += 1
            
            return jsonify({
                'total_records': len(sales_data),
                'date_range': f"{start_date} to {end_date}",
                'dates_with_data': sorted(dates.keys()),
                'first_sale': min(dates.keys()) if dates else None,
                'last_sale': max(dates.keys()) if dates else None,
                'sales_by_date': dates
            })
        else:
            return jsonify({
                'message': 'No sales data found',
                'date_range': f"{start_date} to {end_date}"
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/items')
def debug_items():
    """Get list of items with recent sales for testing"""
    try:
        # Get items from last 90 days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=90)
        
        sales_data = eci_service.get_daily_sales(start_date, end_date)
        
        # Aggregate by item
        item_sales = {}
        for sale in sales_data:
            item_num = sale['item_number']
            if item_num not in item_sales:
                item_sales[item_num] = {
                    'item_number': item_num,
                    'description': sale['description'],
                    'total_quantity': 0,
                    'sale_count': 0,
                    'last_sale': sale['invoice_date'].strftime('%Y-%m-%d')
                }
            item_sales[item_num]['total_quantity'] += sale['quantity']
            item_sales[item_num]['sale_count'] += 1
            
        # Get top 20 items by sale count
        top_items = sorted(
            item_sales.values(), 
            key=lambda x: x['sale_count'], 
            reverse=True
        )[:20]
        
        return jsonify({
            'message': 'Top items with sales history',
            'items': top_items,
            'date_range': f'{start_date} to {end_date}'
        })
        
    except Exception as e:
        logger.error(f"Error getting top items: {str(e)}")
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
    port = int(os.getenv('PORT', 5000))
    app.run(debug=os.getenv('FLASK_ENV') == 'development', host='0.0.0.0', port=port)