# services/eci_api_service.py
import zeep
from zeep import Client
from zeep.transports import Transport
from datetime import datetime, date, timedelta
import logging
from typing import List, Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

class ECIApiService:
    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key
        self.client = self._create_client()
        
    def _create_client(self) -> Client:
        """Create SOAP client for ECI API"""
        wsdl = f"{self.endpoint}?wsdl"
        transport = Transport(timeout=30, operation_timeout=30)
        return Client(wsdl=wsdl, transport=transport)
    
    def get_daily_sales(self, start_date: date, end_date: date) -> List[Dict]:
        """Get all sales for a date range"""
        try:
            # Get invoices for the date range
            invoice_filter = {
                'DateRangeStart': start_date.isoformat(),
                'DateRangeEnd': end_date.isoformat(),
                'InvoiceTypes': [0, 1, 5],  # Ticket, Invoice, Installed Sale
                'RowMaxCount': 999,
                'RowStart': 0
            }
            
            all_invoices = []
            while True:
                response = self.client.service.GetInvoices(
                    apikey=self.api_key,
                    invoicefilter=invoice_filter
                )
                
                if response.Success:
                    invoices = response.Invoices
                    all_invoices.extend(invoices)
                    
                    # Check if there are more results
                    if len(invoices) < 999:
                        break
                    else:
                        invoice_filter['RowStart'] += 999
                else:
                    logger.error(f"Error getting invoices: {response.ErrorMessages}")
                    break
            
            # Get detailed line items for each invoice
            sales_data = []
            for invoice in all_invoices:
                detail_response = self.client.service.GetInvoiceDetail(
                    apikey=self.api_key,
                    docID=invoice.DocID
                )
                
                if detail_response.Success:
                    invoice_detail = detail_response
                    for item in invoice_detail.Items:
                        sales_data.append({
                            'invoice_id': invoice.DocID,
                            'invoice_date': invoice.IssueDate,
                            'account_number': invoice.AccountNumber,
                            'item_number': item.ItemNumber,
                            'description': item.Description,
                            'quantity': float(item.QuantitySold),
                            'unit_price': float(item.UnitPrice) if hasattr(item, 'UnitPrice') else 0,
                            'extended_price': float(item.ExtendedPrice),
                            'branch': invoice.Branch if hasattr(invoice, 'Branch') else None
                        })
            
            return sales_data
            
        except Exception as e:
            logger.error(f"Error in get_daily_sales: {str(e)}")
            return []
    
    def get_inventory_alerts(self, reorder_threshold: int = 10) -> List[Dict]:
        """Get items that need reordering"""
        try:
            item_filter = {
                'RowMaxCount': 999,
                'RowStart': 0,
                'Branch': os.getenv('DEFAULT_BRANCH', 'MAIN')
            }
            
            alerts = []
            while True:
                response = self.client.service.GetItems(
                    apikey=self.api_key,
                    itemFilter=item_filter
                )
                
                if response.Success:
                    items = response.Items
                    
                    for item in items:
                        # Check if quantity available is below threshold
                        qty_available = float(item.QtyAvailable) if item.QtyAvailable >= 0 else 0
                        
                        if qty_available < reorder_threshold and item.TrackOnHand:
                            alerts.append({
                                'item_number': item.ItemNumber,
                                'description': item.Description,
                                'qty_available': qty_available,
                                'qty_on_hand': float(item.QtyOnHand),
                                'on_order': float(item.OnOrder) if hasattr(item, 'OnOrder') else 0,
                                'last_modified': item.LastModifiedDateTime.isoformat() if hasattr(item, 'LastModifiedDateTime') else None,
                                'lead_time': item.LeadTime if hasattr(item, 'LeadTime') else 0
                            })
                    
                    if len(items) < 999:
                        break
                    else:
                        item_filter['RowStart'] += 999
                else:
                    logger.error(f"Error getting items: {response.ErrorMessages}")
                    break
                    
            return sorted(alerts, key=lambda x: x['qty_available'])
            
        except Exception as e:
            logger.error(f"Error in get_inventory_alerts: {str(e)}")
            return []
    
    def get_customer_sales(self, account_number: str, start_date: date, end_date: date) -> Dict:
        """Get sales data for a specific customer"""
        try:
            invoice_filter = {
                'AccountNumber': account_number,
                'DateRangeStart': start_date.isoformat(),
                'DateRangeEnd': end_date.isoformat(),
                'InvoiceTypes': [0, 1, 5],
                'RowMaxCount': 999
            }
            
            response = self.client.service.GetInvoices(
                apikey=self.api_key,
                invoicefilter=invoice_filter
            )
            
            if not response.Success:
                logger.error(f"Error getting customer invoices: {response.ErrorMessages}")
                return {}
            
            # Aggregate sales by item
            item_sales = {}
            total_revenue = 0
            
            for invoice in response.Invoices:
                detail_response = self.client.service.GetInvoiceDetail(
                    apikey=self.api_key,
                    docID=invoice.DocID
                )
                
                if detail_response.Success:
                    for item in detail_response.Items:
                        item_number = item.ItemNumber
                        
                        if item_number not in item_sales:
                            item_sales[item_number] = {
                                'description': item.Description,
                                'quantity': 0,
                                'revenue': 0,
                                'transactions': 0
                            }
                        
                        item_sales[item_number]['quantity'] += float(item.QuantitySold)
                        item_sales[item_number]['revenue'] += float(item.ExtendedPrice)
                        item_sales[item_number]['transactions'] += 1
                        total_revenue += float(item.ExtendedPrice)
            
            # Sort by revenue
            top_items = sorted(
                item_sales.items(),
                key=lambda x: x[1]['revenue'],
                reverse=True
            )[:10]
            
            return {
                'account_number': account_number,
                'period': f"{start_date} to {end_date}",
                'total_revenue': total_revenue,
                'total_items': len(item_sales),
                'top_items': [
                    {
                        'item_number': item[0],
                        **item[1]
                    } for item in top_items
                ]
            }
            
        except Exception as e:
            logger.error(f"Error in get_customer_sales: {str(e)}")
            return {}
    
    def get_all_inventory(self) -> List[Dict]:
        """Get all inventory items with current levels"""
        try:
            item_filter = {
                'RowMaxCount': 999,
                'RowStart': 0,
                'Branch': os.getenv('DEFAULT_BRANCH', 'MAIN')
            }
            
            all_items = []
            while True:
                response = self.client.service.GetItems(
                    apikey=self.api_key,
                    itemFilter=item_filter
                )
                
                if response.Success:
                    items = response.Items
                    
                    for item in items:
                        all_items.append({
                            'item_number': item.ItemNumber,
                            'description': item.Description,
                            'qty_available': float(item.QtyAvailable) if item.QtyAvailable >= 0 else 0,
                            'qty_on_hand': float(item.QtyOnHand),
                            'on_order': float(item.OnOrder) if hasattr(item, 'OnOrder') else 0,
                            'price': float(item.CustomerPrice),
                            'cost': float(item.SOAverageCost) if hasattr(item, 'SOAverageCost') else 0,
                            'last_modified': datetime.now().isoformat()
                        })
                    
                    if len(items) < 999:
                        break
                    else:
                        item_filter['RowStart'] += 999
                else:
                    logger.error(f"Error getting all inventory: {response.ErrorMessages}")
                    break
                    
            return all_items
            
        except Exception as e:
            logger.error(f"Error in get_all_inventory: {str(e)}")
            return []
    
    def get_item_sales_history(self, item_number: str, days: int = 365) -> List[Dict]:
        """Get sales history for a specific item"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # Search for invoices containing this item
            invoice_filter = {
                'DateRangeStart': start_date.isoformat(),
                'DateRangeEnd': end_date.isoformat(),
                'InvoiceTypes': [0, 1, 5],
                'RowMaxCount': 999,
                'SearchText': item_number
            }
            
            response = self.client.service.GetInvoices(
                apikey=self.api_key,
                invoicefilter=invoice_filter
            )
            
            sales_history = []
            
            if response.Success:
                for invoice in response.Invoices:
                    detail_response = self.client.service.GetInvoiceDetail(
                        apikey=self.api_key,
                        docID=invoice.DocID
                    )
                    
                    if detail_response.Success:
                        for item in detail_response.Items:
                            if item.ItemNumber == item_number:
                                sales_history.append({
                                    'date': invoice.IssueDate,
                                    'quantity': float(item.QuantitySold),
                                    'unit_price': float(item.UnitPrice) if hasattr(item, 'UnitPrice') else 0,
                                    'extended_price': float(item.ExtendedPrice),
                                    'account_number': invoice.AccountNumber
                                })
            
            return sorted(sales_history, key=lambda x: x['date'])
            
        except Exception as e:
            logger.error(f"Error in get_item_sales_history: {str(e)}")
            return []