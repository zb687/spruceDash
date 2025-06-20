# services/database_service.py
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, date, timedelta
import logging
from typing import List, Dict, Any, Optional
import os

Base = declarative_base()
logger = logging.getLogger(__name__)

# Database Models
class SalesData(Base):
    __tablename__ = 'sales_data'
    
    id = Column(Integer, primary_key=True)
    invoice_id = Column(String(50), index=True)
    invoice_date = Column(DateTime, index=True)
    account_number = Column(String(50), index=True)
    item_number = Column(String(50), index=True)
    description = Column(String(255))
    quantity = Column(Float)
    unit_price = Column(Float)
    extended_price = Column(Float)
    branch = Column(String(10))
    vendor_code = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_sales_date_item', 'invoice_date', 'item_number'),
        Index('idx_sales_account_date', 'account_number', 'invoice_date'),
    )

class InventoryLevel(Base):
    __tablename__ = 'inventory_levels'
    
    id = Column(Integer, primary_key=True)
    item_number = Column(String(50), unique=True, index=True)
    description = Column(String(255))
    qty_available = Column(Float)
    qty_on_hand = Column(Float)
    on_order = Column(Float)
    reorder_point = Column(Float, default=10)
    lead_time = Column(Integer, default=7)
    last_cost = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
class CustomerMetrics(Base):
    __tablename__ = 'customer_metrics'
    
    id = Column(Integer, primary_key=True)
    account_number = Column(String(50), index=True)
    customer_name = Column(String(255))
    total_revenue = Column(Float)
    total_orders = Column(Integer)
    last_order_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DatabaseService:
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv('DATABASE_URL', 'sqlite:///eci_dashboard.db')
        self.engine = create_engine(self.database_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def store_sales_data(self, sales_data: List[Dict]) -> bool:
        """Store sales data in the database"""
        session = self.Session()
        try:
            for sale in sales_data:
                # Check if record already exists
                existing = session.query(SalesData).filter_by(
                    invoice_id=sale['invoice_id'],
                    item_number=sale['item_number']
                ).first()
                
                if not existing:
                    record = SalesData(
                        invoice_id=sale['invoice_id'],
                        invoice_date=sale['invoice_date'],
                        account_number=sale['account_number'],
                        item_number=sale['item_number'],
                        description=sale.get('description', ''),
                        quantity=sale['quantity'],
                        unit_price=sale.get('unit_price', 0),
                        extended_price=sale['extended_price'],
                        branch=sale.get('branch', ''),
                        vendor_code=sale.get('vendor_code', '')
                    )
                    session.add(record)
            
            session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error storing sales data: {str(e)}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def update_inventory_levels(self, inventory_data: List[Dict]) -> bool:
        """Update inventory levels in the database"""
        session = self.Session()
        try:
            for item in inventory_data:
                # Update or create inventory record
                record = session.query(InventoryLevel).filter_by(
                    item_number=item['item_number']
                ).first()
                
                if record:
                    record.qty_available = item['qty_available']
                    record.qty_on_hand = item['qty_on_hand']
                    record.on_order = item.get('on_order', 0)
                    record.last_cost = item.get('cost', 0)
                    record.last_updated = datetime.utcnow()
                else:
                    record = InventoryLevel(
                        item_number=item['item_number'],
                        description=item.get('description', ''),
                        qty_available=item['qty_available'],
                        qty_on_hand=item['qty_on_hand'],
                        on_order=item.get('on_order', 0),
                        last_cost=item.get('cost', 0)
                    )
                    session.add(record)
            
            session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating inventory levels: {str(e)}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_item_sales_history(self, item_number: str, days: int = 365) -> List[Dict]:
        """Get sales history for an item"""
        session = self.Session()
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            sales = session.query(SalesData).filter(
                SalesData.item_number == item_number,
                SalesData.invoice_date >= start_date
            ).order_by(SalesData.invoice_date).all()
            
            return [
                {
                    'date': sale.invoice_date,
                    'quantity': sale.quantity,
                    'unit_price': sale.unit_price,
                    'extended_price': sale.extended_price,
                    'account_number': sale.account_number
                }
                for sale in sales
            ]
            
        except Exception as e:
            logger.error(f"Error getting item sales history: {str(e)}")
            return []
        finally:
            session.close()
    
    def get_daily_sales_data(self, target_date: date) -> List[Dict]:
        """Get all sales data for a specific date"""
        session = self.Session()
        try:
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())
            
            sales = session.query(SalesData).filter(
                SalesData.invoice_date >= start_datetime,
                SalesData.invoice_date <= end_datetime
            ).all()
            
            return [
                {
                    'invoice_id': sale.invoice_id,
                    'invoice_date': sale.invoice_date,
                    'account_number': sale.account_number,
                    'item_number': sale.item_number,
                    'description': sale.description,
                    'quantity': sale.quantity,
                    'unit_price': sale.unit_price,
                    'extended_price': sale.extended_price,
                    'branch': sale.branch,
                    'vendor_code': sale.vendor_code
                }
                for sale in sales
            ]
            
        except Exception as e:
            logger.error(f"Error getting daily sales data: {str(e)}")
            return []
        finally:
            session.close()
    
    def get_low_inventory_items(self, threshold: int = 10) -> List[Dict]:
        """Get items with inventory below threshold"""
        session = self.Session()
        try:
            items = session.query(InventoryLevel).filter(
                InventoryLevel.qty_available < threshold
            ).order_by(InventoryLevel.qty_available).all()
            
            return [
                {
                    'item_number': item.item_number,
                    'description': item.description,
                    'qty_available': item.qty_available,
                    'qty_on_hand': item.qty_on_hand,
                    'on_order': item.on_order,
                    'reorder_point': item.reorder_point,
                    'lead_time': item.lead_time,
                    'days_of_supply': self._calculate_days_of_supply(item.item_number, item.qty_available)
                }
                for item in items
            ]
            
        except Exception as e:
            logger.error(f"Error getting low inventory items: {str(e)}")
            return []
        finally:
            session.close()
    
    def get_top_customers_by_date(self, target_date: date, limit: int = 10) -> List[Dict]:
        """Get top customers for a specific date"""
        session = self.Session()
        try:
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())
            
            # Query to get top customers by revenue for the date
            from sqlalchemy import func
            
            results = session.query(
                SalesData.account_number,
                func.sum(SalesData.extended_price).label('total_revenue'),
                func.count(func.distinct(SalesData.invoice_id)).label('transactions')
            ).filter(
                SalesData.invoice_date >= start_datetime,
                SalesData.invoice_date <= end_datetime
            ).group_by(
                SalesData.account_number
            ).order_by(
                func.sum(SalesData.extended_price).desc()
            ).limit(limit).all()
            
            return [
                {
                    'account_number': result.account_number,
                    'total_revenue': float(result.total_revenue),
                    'transactions': result.transactions
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Error getting top customers: {str(e)}")
            return []
        finally:
            session.close()
    
    def get_sales_by_vendor(self, start_date: date, end_date: date) -> List[Dict]:
        """Get sales data grouped by vendor"""
        session = self.Session()
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            sales = session.query(SalesData).filter(
                SalesData.invoice_date >= start_datetime,
                SalesData.invoice_date <= end_datetime,
                SalesData.vendor_code.isnot(None)
            ).all()
            
            return [
                {
                    'invoice_id': sale.invoice_id,
                    'item_number': sale.item_number,
                    'vendor_code': sale.vendor_code or 'Unknown',
                    'quantity': sale.quantity,
                    'extended_price': sale.extended_price
                }
                for sale in sales
            ]
            
        except Exception as e:
            logger.error(f"Error getting sales by vendor: {str(e)}")
            return []
        finally:
            session.close()
    
    def _calculate_days_of_supply(self, item_number: str, current_qty: float) -> int:
        """Calculate days of supply based on recent sales"""
        session = self.Session()
        try:
            # Get last 30 days of sales
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            total_sold = session.query(func.sum(SalesData.quantity)).filter(
                SalesData.item_number == item_number,
                SalesData.invoice_date >= thirty_days_ago
            ).scalar() or 0
            
            if total_sold > 0:
                avg_daily_sales = total_sold / 30
                days_of_supply = int(current_qty / avg_daily_sales) if avg_daily_sales > 0 else 999
            else:
                days_of_supply = 999
            
            return days_of_supply
            
        except Exception as e:
            logger.error(f"Error calculating days of supply: {str(e)}")
            return 0
        finally:
            session.close()