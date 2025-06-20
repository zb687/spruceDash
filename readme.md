# ECI Spruce Dashboard

A comprehensive dashboard for ECI Spruce POS system that provides real-time insights, demand forecasting, and inventory management alerts.

## Features

### 📊 Real-Time Analytics
- Daily sales metrics and revenue tracking
- Transaction counts and average order values
- Hourly sales patterns

### 📈 Demand Forecasting
- AI-powered demand predictions using historical data
- Moving average calculations (7, 30, 90 days)
- Trend analysis and seasonality detection
- Reorder point calculations with safety stock

### 📦 Inventory Management
- Low stock alerts with days-of-supply calculations
- Real-time inventory levels
- Automatic reorder point suggestions
- Lead time considerations

### 👥 Customer Analytics
- Top customers by revenue
- Customer purchase patterns
- Sales by customer account

### 🏷️ Brand Performance
- Sales breakdown by vendor/brand
- Brand performance comparisons
- Revenue contribution analysis

## Technical Stack

- **Backend**: Python Flask, SQLAlchemy
- **API Integration**: SOAP/Zeep for ECI API
- **Database**: PostgreSQL (production) / SQLite (development)
- **Caching**: Redis
- **Analytics**: Pandas, NumPy
- **Visualization**: Plotly.js
- **Frontend**: Bootstrap 5, Vanilla JavaScript
- **Deployment**: Heroku/Railway/Render ready

## Quick Start

### Local Development

1. Clone the repository
```bash
git clone <your-repo-url>
cd eci-spruce-dashboard
```

2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Configure environment
```bash
cp .env.example .env
# Edit .env with your ECI API credentials
```

5. Run the application
```bash
python app.py
```

6. Open browser to `http://localhost:5000`

### Docker Deployment

```bash
docker-compose up -d
```

## Configuration

Required environment variables:
- `ECI_API_ENDPOINT`: Your ECI API endpoint URL
- `ECI_API_KEY`: Your ECI API key
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string
- `DEFAULT_BRANCH`: Default branch code for inventory

## API Endpoints

- `GET /api/dashboard/summary` - Dashboard summary metrics
- `GET /api/inventory/alerts` - Low inventory alerts
- `GET /api/sales/by-customer?account_number=XXX` - Customer sales data
- `GET /api/sales/by-brand` - Brand performance data
- `GET /api/demand/forecast/<item_number>` - Item demand forecast
- `GET /api/reports/daily` - Daily report generation

## Dashboard Features

### Main Dashboard
- Real-time metrics cards
- Top selling items table
- Inventory alerts with action buttons
- 30-day sales trend chart
- Brand performance pie chart

### Demand Forecast Tool
- Item-specific demand analysis
- Visual forecast charts
- Reorder recommendations
- Trend indicators

## Scheduled Tasks

The application includes automated tasks:
- **Daily Data Collection** (2 AM): Fetches previous day's sales and updates inventory
- **Cache Refresh**: Automatic cache invalidation every 5 minutes for real-time data

## Performance Optimization

- Redis caching for frequently accessed data
- Database indexes on commonly queried fields
- Pagination for large result sets
- Async data loading on frontend

## Security

- API key authentication
- Environment-based configuration
- SQL injection prevention via SQLAlchemy ORM
- XSS protection with proper HTML escaping

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - feel free to use this in your business

## Support

For issues or questions:
- Check the deployment guide
- Review error logs
- Ensure API credentials are correct
- Verify network connectivity to ECI servers