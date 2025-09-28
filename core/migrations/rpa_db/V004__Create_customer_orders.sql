-- Migration V004: Create customer_orders table for order processing workflows
-- This table stores order data processed by RPA flows

CREATE TABLE IF NOT EXISTS customer_orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL UNIQUE,
    customer_id VARCHAR(50) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    product VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price > 0),
    subtotal DECIMAL(10, 2) NOT NULL,
    tax_amount DECIMAL(10, 2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(10, 2) NOT NULL DEFAULT 0,
    total_amount DECIMAL(10, 2) NOT NULL,
    order_date DATE NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    region VARCHAR(50) NOT NULL,
    fulfillment_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    processed_by_flow VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_customer_orders_order_id ON customer_orders(order_id);
CREATE INDEX IF NOT EXISTS idx_customer_orders_customer_id ON customer_orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_orders_order_date ON customer_orders(order_date);
CREATE INDEX IF NOT EXISTS idx_customer_orders_priority ON customer_orders(priority);
CREATE INDEX IF NOT EXISTS idx_customer_orders_region ON customer_orders(region);
CREATE INDEX IF NOT EXISTS idx_customer_orders_status ON customer_orders(fulfillment_status);
CREATE INDEX IF NOT EXISTS idx_customer_orders_processed_by ON customer_orders(processed_by_flow);

-- Create composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_customer_orders_date_status ON customer_orders(order_date, fulfillment_status);
CREATE INDEX IF NOT EXISTS idx_customer_orders_region_priority ON customer_orders(region, priority);

-- Insert sample order data
INSERT INTO customer_orders (
    order_id, customer_id, customer_name, product, quantity, unit_price, 
    subtotal, tax_amount, discount_amount, total_amount, order_date, 
    priority, region, fulfillment_status, processed_by_flow
) VALUES
('ORD-001', 'CUST-001', 'Alice Johnson', 'Premium Widget A', 2, 25.50, 51.00, 4.08, 5.10, 49.98, '2024-01-15', 'high', 'North', 'completed', 'rpa3-concurrent-processing'),
('ORD-002', 'CUST-002', 'Bob Smith', 'Standard Widget B', 5, 15.75, 78.75, 5.51, 3.94, 80.32, '2024-01-15', 'medium', 'South', 'completed', 'rpa3-concurrent-processing'),
('ORD-003', 'CUST-003', 'Charlie Brown', 'Budget Widget C', 10, 8.99, 89.90, 8.09, 0.00, 97.99, '2024-01-16', 'low', 'East', 'pending', 'rpa3-concurrent-processing'),
('ORD-004', 'CUST-004', 'Diana Prince', 'Premium Widget A', 1, 25.50, 25.50, 2.04, 2.55, 24.99, '2024-01-16', 'high', 'West', 'completed', 'rpa3-concurrent-processing'),
('ORD-005', 'CUST-005', 'Eve Wilson', 'Standard Widget B', 3, 15.75, 47.25, 3.78, 2.36, 48.67, '2024-01-17', 'medium', 'North', 'shipped', 'rpa3-concurrent-processing');