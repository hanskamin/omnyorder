#!/usr/bin/env python3
"""
Simple HTTP API Server for Browser-Use Shopping
Provides a REST API for remote agent invocation
"""

import asyncio
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

from main import shop_for_items, process_structured_shopping_request, SiteType, get_site_config, OrderItem, Order, ShoppingRequest as MainShoppingRequest

# Create FastAPI app
app = FastAPI(
    title="Browser-Use Shopping API",
    description="REST API for remote shopping automation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class ShoppingRequest(BaseModel):
    items: List[str]
    site: str = "instacart"

class ShoppingResponse(BaseModel):
    success: bool
    site: str
    total_items: int
    total_price: float
    items: List[dict]
    error: Optional[str] = None

class StructuredShoppingRequest(BaseModel):
    budget: Optional[str] = None
    dietary_restrictions: List[str] = []
    orders: List[Order]

class StructuredShoppingResponse(BaseModel):
    success: bool
    budget: Optional[str]
    dietary_restrictions: List[str]
    orders: List[dict]
    total_orders: int
    successful_orders: int
    failed_orders: int

class SiteInfoResponse(BaseModel):
    site: str
    name: str
    url: str
    description: str

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Browser-Use Shopping API",
        "version": "1.0.0",
        "endpoints": {
            "POST /shop": "Shop for items (legacy format)",
            "POST /shop/structured": "Shop for items (structured format)",
            "GET /sites": "Get supported sites",
            "GET /sites/{site}": "Get site information",
            "GET /health": "Health check"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "browser-use-shopping"}

@app.get("/sites")
async def get_sites():
    """Get all supported shopping sites"""
    sites = []
    for site in SiteType:
        config = get_site_config(site)
        sites.append({
            "site": site.value,
            "name": config["name"],
            "url": config["url"],
            "description": config["description"]
        })
    return {"sites": sites}

@app.get("/sites/{site}")
async def get_site_info(site: str):
    """Get information about a specific site"""
    try:
        site_enum = SiteType(site)
        config = get_site_config(site_enum)
        return SiteInfoResponse(
            site=site,
            name=config["name"],
            url=config["url"],
            description=config["description"]
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid site: {site}")

@app.post("/shop", response_model=ShoppingResponse)
async def shop_for_items_endpoint(request: ShoppingRequest):
    """Shop for items on specified site"""
    try:
        # Validate site
        try:
            SiteType(request.site)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid site: {request.site}")
        
        # Call the shopping function
        result = await shop_for_items(request.items, request.site)
        
        if result["success"]:
            return ShoppingResponse(
                success=True,
                site=result["site"],
                total_items=result["total_items"],
                total_price=result["total_price"],
                items=result["items"]
            )
        else:
            return ShoppingResponse(
                success=False,
                site=request.site,
                total_items=0,
                total_price=0.0,
                items=[],
                error=result["error"]
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/shop/structured", response_model=StructuredShoppingResponse)
async def shop_structured_endpoint(request: StructuredShoppingRequest):
    """Shop for items using structured request format"""
    try:
        # Convert to main shopping request
        main_request = MainShoppingRequest(
            budget=request.budget,
            dietary_restrictions=request.dietary_restrictions,
            orders=request.orders
        )
        
        # Call the structured shopping function
        result = await process_structured_shopping_request(main_request)
        
        return StructuredShoppingResponse(
            success=result["success"],
            budget=result["budget"],
            dietary_restrictions=result["dietary_restrictions"],
            orders=result["orders"],
            total_orders=result["total_orders"],
            successful_orders=result["successful_orders"],
            failed_orders=result["failed_orders"]
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    print("🚀 Starting Browser-Use Shopping API Server")
    print("📡 Server will be available at: http://localhost:8000")
    print("📚 API documentation at: http://localhost:8000/docs")
    print("🔍 Health check at: http://localhost:8000/health")
    
    uvicorn.run(
        "simple_api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
