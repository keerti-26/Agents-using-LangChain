"""
Assignment 1: The Context Overflow Tool
========================================
This customer support agent has a tool that looks up order information.
Problem: The tool returns the ENTIRE orders database every single time.

Run this and observe the failure:
    python starter.py

Your job: Fix the tool so it returns only what's needed.
"""

import json
import random
import string
from datetime import datetime, timedelta
import os
import uuid
import re
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from dotenv import load_dotenv
load_dotenv()


# ---------------------------------------------------------------------------
# Simulated database
# ---------------------------------------------------------------------------

def _generate_fake_orders(n=10000):
    """Generate a large fake orders table."""
    statuses = ["shipped", "delivered", "processing", "returned", "cancelled"]
    products = [
        "Wireless Mouse", "USB-C Hub", "Mechanical Keyboard", "Monitor Stand",
        "Webcam HD", "Desk Lamp", "Laptop Sleeve", "Cable Organizer",
        "Noise-Cancelling Headphones", "Portable Charger", "Ergonomic Chair",
        "Standing Desk Mat", "Blue Light Glasses", "Wireless Charger",
        "Smart Power Strip", "Document Scanner", "Label Printer",
    ]
    customers = [f"customer_{i:04d}" for i in range(500)]
    orders = []
    for i in range(n):
        order_date = datetime.now() - timedelta(days=random.randint(1, 365))
        items = random.sample(products, k=random.randint(1, 5))
        orders.append({
            "order_id": f"ORD-{i+1:06d}",
            "customer_id": random.choice(customers),
            "customer_email": f"user{random.randint(1,9999)}@example.com",
            "status": random.choice(statuses),
            "order_date": order_date.isoformat(),
            "delivery_date": (order_date + timedelta(days=random.randint(2, 14))).isoformat(),
            "items": items,
            "quantities": [random.randint(1, 3) for _ in items],
            "prices": [round(random.uniform(9.99, 299.99), 2) for _ in items],
            "shipping_address": {
                "street": f"{random.randint(1,9999)} {random.choice(['Main', 'Oak', 'Elm', 'Pine', 'Cedar'])} St",
                "city": random.choice(["Portland", "Austin", "Denver", "Seattle", "Chicago"]),
                "state": random.choice(["OR", "TX", "CO", "WA", "IL"]),
                "zip": f"{random.randint(10000, 99999)}",
            },
            "payment_method": random.choice(["credit_card", "debit_card", "paypal"]),
            "card_last_four": ''.join(random.choices(string.digits, k=4)),
            "internal_notes": f"Batch processed. Agent: auto-{random.randint(1,50)}. "
                              f"Priority: {''.join(random.choices(string.ascii_lowercase, k=200))}",
            "warehouse_log": f"Picked from aisle {random.randint(1,99)}, "
                             f"shelf {random.choice(string.ascii_uppercase)}{random.randint(1,20)}. "
                             f"Weight: {round(random.uniform(0.5, 25.0), 2)}kg. "
                             f"Dimensions: {random.randint(10,80)}x{random.randint(10,80)}x{random.randint(10,80)}cm. "
                             f"Tracking events: {'|'.join([f'event_{j}' for j in range(random.randint(5,20))])}",
        })
    return orders


ORDERS_DB = _generate_fake_orders(2000)

# Seed a known order so we can test with it
ORDERS_DB[0] = {
    "order_id": "ORD-000001",
    "customer_id": "customer_0042",
    "customer_email": "alice@example.com",
    "status": "shipped",
    "order_date": "2026-03-15T10:30:00",
    "delivery_date": "2026-03-22T14:00:00",
    "items": ["Mechanical Keyboard", "USB-C Hub"],
    "quantities": [1, 2],
    "prices": [149.99, 34.99],
    "shipping_address": {
        "street": "742 Evergreen Terrace",
        "city": "Portland",
        "state": "OR",
        "zip": "97201",
    },
    "payment_method": "credit_card",
    "card_last_four": "4242",
    "internal_notes": "VIP customer, handle with care. Escalation history: ...",
    "warehouse_log": "Picked from aisle 12, shelf B7. Weight: 2.3kg. ...",
}


# ---------------------------------------------------------------------------
# 🐛 THE BROKEN TOOL has been fixed here
# ---------------------------------------------------------------------------

@tool
def lookup_order_info(query: str) -> str:
    
    """Look up order information from the database. Use this tool  when a customer asks about their order status,
    delivery date, or order details. Only return details that customer is asking for dont give additional details

    Args:
        query: The customer's question about their order.
    """
    MAX_OUTPUT_CHARS = 500 
    MAX_EMAIL_RESULTS = 5
    #Extracting details
    order_match = re.search(r"ORD-\d{6}", query.upper())
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", query.lower())

    search_id = order_match.group(0) if order_match else None
    search_email = email_match.group(0) if email_match else None

    query_lower = query.lower()
    order_status = "status" in query_lower
    order_delivery = any(w in query_lower for w in ["delivered", "when"])
    order_items = "items" in query_lower

    if order_status:
        fields = ["order_id", "status"]
    elif order_delivery:
        fields = ["order_id", "delivery_date"]
    elif order_items:
        fields = ["order_id", "items"]
    else:
        fields = ["order_id"]

    if not search_id and not search_email:
        return f"No matching order_id or email found in query"
    # print(search_id)
    result=[]
    for order in ORDERS_DB:
       if (search_id and search_id == order["order_id"]) or (search_email and search_email == order["customer_email"]):
            result.append({k: order[k] for k in fields if k in order})
    if not result:
        return f"No order available for {query}"
    #Limit email results
    if search_email and len(result) >MAX_EMAIL_RESULTS:
        result = result[:MAX_EMAIL_RESULTS]
    output = result[0] if search_id else result
    #Summarize large output
    if isinstance(output, list) and len(output) > 3:
        output = {
            "summary": f"{len(output)} orders found",
            "statuses": list({o["status"] for o in output}),
            "order_ids": [o["order_id"] for o in output]
        }
    #Truncate with warning if still too long
    json_output = json.dumps(output)
    if len(json_output) > MAX_OUTPUT_CHARS:
        truncated = json_output[:MAX_OUTPUT_CHARS]
        return truncated + '... [OUTPUT TRUNCATED - response exceeded limit]'

    return json_output

# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

def create_agent():
    session_id = str(uuid.uuid4())
    llm = ChatOpenAI(
        model='gpt-4o-mini',
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("BASE_URL"),
        streaming=True,
        default_headers={
            "X-Session-ID": session_id
        }
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a helpful customer support agent. "
         "1. Always use the lookup_order_info tool to find information about customer orders. "
         "2. Do not return the raw json"
         "3. Answer the question directly and be concise and short. Dont give additional details"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, [lookup_order_info], prompt)
    return AgentExecutor(agent=agent, tools=[lookup_order_info], verbose=False)


# ---------------------------------------------------------------------------
# Test queries
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    "What's the status of order ORD-000001?",
    "When will order ORD-000001 be delivered?",
    "What items are in order ORD-000001?",
    "Can you look up the order for customer alice@example.com?",
]


def main():
    agent = create_agent()

    for query in TEST_QUERIES:
        print(f"\n{'='*60}")
        print(f"QUERY: {query}")
        print(f"{'='*60}")
        try:
            result = agent.invoke({"input": query})
            print(f"\nRESPONSE: {result['output']}")
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
        print()


if __name__ == "__main__":
    main()
