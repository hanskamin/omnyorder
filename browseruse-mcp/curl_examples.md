# Browser-Use Shopping API - cURL Examples

This document provides sample cURL commands for both the legacy and new structured shopping request formats.

## Server Setup

First, start the API server:
```bash
python simple_api_server.py
```

The server will be available at `http://localhost:8000`

## API Endpoints

- `POST /shop` - Legacy format (simple items list)
- `POST /shop/structured` - New structured format (multiple platforms, detailed items)
- `GET /sites` - Get supported shopping sites
- `GET /health` - Health check

## 1. Legacy Format (Simple Items List)

### Basic Shopping Request
```bash
curl -X POST "http://localhost:8000/shop" \
  -H "Content-Type: application/json" \
  -d '{
    "items": ["milk", "eggs", "bread"],
    "site": "instacart"
  }'
```

### Uber Eats Request
```bash
curl -X POST "http://localhost:8000/shop" \
  -H "Content-Type: application/json" \
  -d '{
    "items": ["pizza", "burger", "fries"],
    "site": "ubereats"
  }'
```

## 2. New Structured Format (Multiple Platforms)

### Complex Multi-Platform Shopping Request
```bash
curl -X POST "http://localhost:8000/shop/structured" \
  -H "Content-Type: application/json" \
  -d '{
    "budget": 50.0,
    "dietary_restrictions": ["vegetarian"],
    "orders": [
      {
        "platform": "Instacart",
        "items": [
          {
            "name": "Roma Tomatoes",
            "quantity": "2 lbs",
            "details": ""
          },
          {
            "name": "Garlic",
            "quantity": "1 bulb",
            "details": ""
          },
          {
            "name": "Fresh Basil",
            "quantity": "1 bunch",
            "details": ""
          },
          {
            "name": "Spaghetti Pasta",
            "quantity": "1 box",
            "details": "16 oz"
          }
        ]
      },
      {
        "platform": "Uber Eats",
        "items": [
          {
            "name": "Strawberry Banana Smoothie",
            "quantity": "1",
            "details": "Medium, 16oz"
          },
          {
            "name": "Turkey and Swiss Sandwich",
            "quantity": "1",
            "details": "On whole wheat bread"
          }
        ]
      }
    ]
  }'
```

### Simple Single Platform Request
```bash
curl -X POST "http://localhost:8000/shop/structured" \
  -H "Content-Type: application/json" \
  -d '{
    "budget": 25.0,
    "dietary_restrictions": [],
    "orders": [
      {
        "platform": "Instacart",
        "items": [
          {
            "name": "Organic Milk",
            "quantity": "1 gallon",
            "details": "Whole milk"
          },
          {
            "name": "Free Range Eggs",
            "quantity": "1 dozen",
            "details": "Large eggs"
          }
        ]
      }
    ]
  }'
```

### DoorDash Food Order
```bash
curl -X POST "http://localhost:8000/shop/structured" \
  -H "Content-Type: application/json" \
  -d '{
    "budget": 30.0,
    "dietary_restrictions": ["gluten-free"],
    "orders": [
      {
        "platform": "DoorDash",
        "items": [
          {
            "name": "Grilled Chicken Salad",
            "quantity": "1",
            "details": "No croutons, gluten-free dressing"
          },
          {
            "name": "Quinoa Bowl",
            "quantity": "1",
            "details": "With vegetables and tahini sauce"
          }
        ]
      }
    ]
  }'
```

## 3. Utility Endpoints

### Health Check
```bash
curl -X GET "http://localhost:8000/health"
```

### Get All Supported Sites
```bash
curl -X GET "http://localhost:8000/sites"
```

### Get Site Information
```bash
curl -X GET "http://localhost:8000/sites/instacart"
```

### API Documentation
Visit `http://localhost:8000/docs` in your browser for interactive API documentation.

## Expected Response Formats

### Legacy Format Response
```json
{
  "success": true,
  "site": "instacart",
  "total_items": 3,
  "total_price": 15.50,
  "items": [
    {
      "name": "Organic Milk",
      "price": 4.99,
      "brand": "Horizon",
      "size": "1 gallon",
      "url": "https://www.instacart.com/...",
      "site": "instacart"
    }
  ]
}
```

### Structured Format Response
```json
{
  "success": true,
  "budget": 50.0,
  "dietary_restrictions": ["vegetarian"],
  "orders": [
    {
      "platform": "Instacart",
      "success": true,
      "items": [
        {
          "name": "Roma Tomatoes",
          "price": 3.99,
          "brand": "Fresh Market",
          "size": "2 lbs",
          "url": "https://www.instacart.com/..."
        }
      ],
      "total_items": 4,
      "total_price": 18.50,
      "error": null
    },
    {
      "platform": "Uber Eats",
      "success": true,
      "items": [
        {
          "name": "Strawberry Banana Smoothie",
          "price": 6.99,
          "brand": "Smoothie King",
          "size": "Medium",
          "url": "https://www.ubereats.com/..."
        }
      ],
      "total_items": 2,
      "total_price": 12.50,
      "error": null
    }
  ],
  "total_orders": 2,
  "successful_orders": 2,
  "failed_orders": 0
}
```

## Error Handling

### Invalid Site
```bash
curl -X POST "http://localhost:8000/shop" \
  -H "Content-Type: application/json" \
  -d '{
    "items": ["milk"],
    "site": "invalid_site"
  }'
```

### Malformed Request
```bash
curl -X POST "http://localhost:8000/shop/structured" \
  -H "Content-Type: application/json" \
  -d '{
    "budget": "invalid_budget",
    "orders": []
  }'
```

## Notes

- The API supports both legacy and new structured formats
- Budget and dietary restrictions are optional in structured format
- Platform names are case-insensitive and support variations (e.g., "Uber Eats", "ubereats", "UberEats")
- All monetary values should be in USD
- The API will attempt to process all orders even if some fail
- Check the response for individual order success/failure status
