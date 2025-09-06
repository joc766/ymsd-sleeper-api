"""
AWS Lambda handler for YMSD Sleeper API

This module provides the Lambda handler for the FastAPI application
using Mangum adapter for AWS Lambda integration.
"""

import logging
from mangum import Mangum
from main import app

# Configure logging for Lambda
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Mangum handler
handler = Mangum(app, lifespan="off")

# Lambda handler function
def lambda_handler(event, context):
    """
    AWS Lambda handler function
    
    Args:
        event: Lambda event object
        context: Lambda context object
        
    Returns:
        API Gateway response
    """
    try:
        # Log the incoming request
        logger.info(f"Processing request: {event.get('httpMethod', 'UNKNOWN')} {event.get('path', 'UNKNOWN')}")
        
        # Process the request through Mangum
        response = handler(event, context)
        
        # Log response status
        if isinstance(response, dict) and 'statusCode' in response:
            logger.info(f"Response status: {response['statusCode']}")
        
        return response
        
    except Exception as e:
        logger.error(f"Lambda handler error: {e}", exc_info=True)
        
        # Return error response
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'
            },
            'body': '{"error": "Internal server error", "detail": "An unexpected error occurred"}'
        }
