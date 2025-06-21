# services/analytics_service.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import logging
from database_service import DatabaseService
import plotly.graph_objs as go
import plotly.utils
import json

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self):
        self.db_service = DatabaseService()
    
    def calculate_daily_sales(self, sales_data: List[Dict]) -> Dict:
        """Calculate daily sales metrics"""
        if not sales_data:
            return {
                'total_revenue': 0,
                'total_transactions': 0,
                'average_transaction': 0,
                'items_sold': 0
            }
        
        df = pd.DataFrame(sales_data)
        
        return {
            'total_revenue': float(df['extended_price'].sum()),
            'total_transactions': df['invoice_id'].nunique(),
            'average_transaction': float(df.groupby('invoice_id')['extended_price'].sum().mean()),
            'items_sold': int(df['quantity'].sum())
        }
    
    def get_top_items(self, sales_data: List[Dict], limit: int = 10) -> List[Dict]:
        """Get top selling items by revenue"""
        if not sales_data:
            return []
        
        df = pd.DataFrame(sales_data)
        
        # Group by item and aggregate
        item_summary = df.groupby(['item_number', 'description']).agg({
            'quantity': 'sum',
            'extended_price': 'sum',
            'invoice_id': 'nunique'
        }).reset_index()
        
        item_summary.columns = ['item_number', 'description', 'quantity_sold', 'revenue', 'transactions']
        
        # Sort by revenue and get top items
        top_items = item_summary.nlargest(limit, 'revenue')
        
        return top_items.to_dict('records')
    
    def calculate_demand_forecast(self, item_number: str, days_history: int = 365) -> Dict:
        """Calculate demand forecast for an item using moving averages and trend analysis"""
        try:
            # Get historical sales data from database
            sales_history = self.db_service.get_item_sales_history(item_number, days_history)
            
            if not sales_history:
                return {
                    'item_number': item_number,
                    'forecast': None,
                    'message': 'Insufficient historical data'
                }
            
            # Convert to DataFrame
            df = pd.DataFrame(sales_history)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            
            # Resample to daily data (fill missing days with 0)
            daily_sales = df['quantity'].resample('D').sum().fillna(0)
            
            # Calculate moving averages
            ma_7 = daily_sales.rolling(window=7).mean()
            ma_30 = daily_sales.rolling(window=30).mean()
            ma_90 = daily_sales.rolling(window=90).mean()
            
            # Calculate trend
            if len(daily_sales) >= 30:
                # Use linear regression for trend
                x = np.arange(len(daily_sales))
                y = daily_sales.values
                
                # Remove zeros for better trend calculation
                mask = y > 0
                if mask.sum() > 10:  # Need at least 10 non-zero days
                    x_filtered = x[mask]
                    y_filtered = y[mask]
                    
                    # Calculate trend
                    z = np.polyfit(x_filtered, y_filtered, 1)
                    trend_slope = z[0]
                else:
                    trend_slope = 0
            else:
                trend_slope = 0
            
            # Calculate seasonality (day of week patterns)
            dow_pattern = daily_sales.groupby(daily_sales.index.dayofweek).mean()
            
            # Current metrics
            current_avg_daily = float(ma_7.iloc[-1]) if not ma_7.empty and not np.isnan(ma_7.iloc[-1]) else 0
            current_avg_weekly = current_avg_daily * 7
            current_avg_monthly = float(ma_30.iloc[-1]) * 30 if not ma_30.empty and not np.isnan(ma_30.iloc[-1]) else 0
            
            # Forecast next 30 days
            forecast_30_days = current_avg_daily * 30 * (1 + trend_slope * 0.1)  # Adjust for trend
            
            # Calculate reorder point (7-day lead time + safety stock)
            lead_time_demand = current_avg_daily * 7
            safety_stock = current_avg_daily * 3  # 3 days safety stock
            reorder_point = lead_time_demand + safety_stock
            
            # Create visualization data
            chart_data = self._create_forecast_chart(daily_sales, ma_7, ma_30, ma_90)
            
            return {
                'item_number': item_number,
                'current_metrics': {
                    'avg_daily_demand': round(current_avg_daily, 2),
                    'avg_weekly_demand': round(current_avg_weekly, 2),
                    'avg_monthly_demand': round(current_avg_monthly, 2)
                },
                'forecast': {
                    'next_7_days': round(current_avg_daily * 7, 2),
                    'next_30_days': round(forecast_30_days, 2),
                    'trend': 'increasing' if trend_slope > 0.1 else 'decreasing' if trend_slope < -0.1 else 'stable',
                    'trend_percentage': round(trend_slope * 100, 2)
                },
                'inventory_planning': {
                    'reorder_point': round(reorder_point, 0),
                    'safety_stock': round(safety_stock, 0),
                    'lead_time_demand': round(lead_time_demand, 0)
                },
                'seasonality': {
                    'day_of_week_pattern': dow_pattern.to_dict()
                },
                'chart_data': chart_data
            }
            
        except Exception as e:
            logger.error(f"Error calculating demand forecast: {str(e)}")
            return {
                'item_number': item_number,
                'forecast': None,
                'error': str(e)
            }
    
    def get_sales_by_brand(self, start_date: date, end_date: date) -> List[Dict]:
        """Get sales aggregated by brand/vendor"""
        try:
            # Get sales data with vendor information
            sales_data = self.db_service.get_sales_by_vendor(start_date, end_date)
            
            if not sales_data:
                return []
            
            df = pd.DataFrame(sales_data)
            
            # Group by vendor/brand
            brand_summary = df.groupby('vendor_code').agg({
                'quantity': 'sum',
                'extended_price': 'sum',
                'item_number': 'nunique',
                'invoice_id': 'nunique'
            }).reset_index()
            
            brand_summary.columns = ['brand', 'units_sold', 'revenue', 'unique_items', 'transactions']
            
            # Calculate percentages
            total_revenue = brand_summary['revenue'].sum()
            brand_summary['revenue_percentage'] = (brand_summary['revenue'] / total_revenue * 100).round(2)
            
            # Sort by revenue
            brand_summary = brand_summary.sort_values('revenue', ascending=False)
            
            return brand_summary.to_dict('records')
            
        except Exception as e:
            logger.error(f"Error getting sales by brand: {str(e)}")
            return []
    
    def generate_daily_report(self, report_date: str) -> Dict:
        """Generate comprehensive daily report"""
        try:
            date = datetime.strptime(report_date, '%Y-%m-%d').date()
            
            # Get various metrics
            sales_data = self.db_service.get_daily_sales_data(date)
            inventory_alerts = self.db_service.get_low_inventory_items()
            top_customers = self.db_service.get_top_customers_by_date(date, limit=10)
            
            # Calculate metrics
            daily_metrics = self.calculate_daily_sales(sales_data)
            top_items = self.get_top_items(sales_data, limit=10)
            
            # Compare to previous period
            prev_date = date - timedelta(days=1)
            prev_sales_data = self.db_service.get_daily_sales_data(prev_date)
            prev_metrics = self.calculate_daily_sales(prev_sales_data)
            
            # Calculate changes
            revenue_change = ((daily_metrics['total_revenue'] - prev_metrics['total_revenue']) / 
                            prev_metrics['total_revenue'] * 100) if prev_metrics['total_revenue'] > 0 else 0
            
            return {
                'report_date': report_date,
                'summary': {
                    'total_revenue': daily_metrics['total_revenue'],
                    'total_transactions': daily_metrics['total_transactions'],
                    'average_transaction': daily_metrics['average_transaction'],
                    'items_sold': daily_metrics['items_sold'],
                    'revenue_change_percentage': round(revenue_change, 2)
                },
                'top_selling_items': top_items,
                'inventory_alerts': inventory_alerts[:10],
                'top_customers': top_customers,
                'charts': {
                    'hourly_sales': self._get_hourly_sales_chart(sales_data),
                    'category_breakdown': self._get_category_breakdown_chart(sales_data)
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating daily report: {str(e)}")
            return {'error': str(e)}
    
    def _create_forecast_chart(self, daily_sales, ma_7, ma_30, ma_90):
        """Create forecast visualization data"""
        try:
            # Create traces
            traces = [
                go.Scatter(
                    x=daily_sales.index.tolist(),
                    y=daily_sales.values.tolist(),
                    mode='lines',
                    name='Daily Sales',
                    line=dict(color='lightgray', width=1)
                ),
                go.Scatter(
                    x=ma_7.index.tolist(),
                    y=ma_7.values.tolist(),
                    mode='lines',
                    name='7-Day MA',
                    line=dict(color='blue', width=2)
                ),
                go.Scatter(
                    x=ma_30.index.tolist(),
                    y=ma_30.values.tolist(),
                    mode='lines',
                    name='30-Day MA',
                    line=dict(color='green', width=2)
                ),
                go.Scatter(
                    x=ma_90.index.tolist(),
                    y=ma_90.values.tolist(),
                    mode='lines',
                    name='90-Day MA',
                    line=dict(color='red', width=2)
                )
            ]
            
            # Convert to JSON
            graphJSON = json.dumps(traces, cls=plotly.utils.PlotlyJSONEncoder)
            
            return graphJSON
            
        except Exception as e:
            logger.error(f"Error creating forecast chart: {str(e)}")
            return None
    
    def _get_hourly_sales_chart(self, sales_data: List[Dict]) -> str:
        """Create hourly sales chart data"""
        try:
            if not sales_data:
                return None
                
            df = pd.DataFrame(sales_data)
            df['hour'] = pd.to_datetime(df['invoice_date']).dt.hour
            
            hourly_sales = df.groupby('hour')['extended_price'].sum().reset_index()
            
            trace = go.Bar(
                x=hourly_sales['hour'].tolist(),
                y=hourly_sales['extended_price'].tolist(),
                marker=dict(color='blue')
            )
            
            return json.dumps([trace], cls=plotly.utils.PlotlyJSONEncoder)
            
        except Exception as e:
            logger.error(f"Error creating hourly sales chart: {str(e)}")
            return None
    
    def _get_category_breakdown_chart(self, sales_data: List[Dict]) -> str:
        """Create category breakdown pie chart"""
        try:
            if not sales_data:
                return None
                
            df = pd.DataFrame(sales_data)
            
            # Group by description (or you could use actual categories if available)
            category_sales = df.groupby('description')['extended_price'].sum().nlargest(10)
            
            trace = go.Pie(
                labels=category_sales.index.tolist(),
                values=category_sales.values.tolist()
            )
            
            return json.dumps([trace], cls=plotly.utils.PlotlyJSONEncoder)
            
        except Exception as e:
            logger.error(f"Error creating category breakdown chart: {str(e)}")
            return None
