-- PeruRE Property Database Schema
-- Run automatically by docker-compose postgres init

CREATE EXTENSION IF NOT EXISTS postgis;

-- Properties / Listings
CREATE TABLE IF NOT EXISTS properties (
    id TEXT PRIMARY KEY,
    address TEXT NOT NULL,
    district TEXT NOT NULL,
    price_usd NUMERIC NOT NULL,
    sqm NUMERIC,
    bedrooms INTEGER,
    bathrooms INTEGER,
    type TEXT CHECK (type IN ('apartment', 'house', 'office', 'land')),
    status TEXT DEFAULT 'available' CHECK (status IN ('available', 'sold', 'rented', 'withdrawn')),
    features JSONB DEFAULT '[]',
    location GEOGRAPHY(POINT, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Clients / Leads
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    budget_usd NUMERIC,
    preferred_districts TEXT[] DEFAULT '{}',
    property_type TEXT CHECK (property_type IN ('apartment', 'house', 'office', 'land')),
    financing_status TEXT CHECK (financing_status IN ('cash', 'pre_approved', 'pending', 'unknown')),
    financing_score INTEGER CHECK (financing_score BETWEEN 0 AND 100),
    documents_status JSONB DEFAULT '{}',
    status TEXT DEFAULT 'new' CHECK (status IN ('new', 'qualified', 'needs_docs', 'waitlist', 'closed')),
    do_not_contact BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Appointments / Calendar
CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    broker_id TEXT NOT NULL,
    client_id TEXT REFERENCES clients(id),
    property_id TEXT REFERENCES properties(id),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    appointment_type TEXT CHECK (appointment_type IN ('showing', 'follow_up', 'docs_review', 'closing')),
    status TEXT DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'tentative', 'cancelled', 'completed')),
    cancellation_reason TEXT,
    location GEOGRAPHY(POINT, 4326),
    address TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Matches (lead-property pairings)
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    client_id TEXT REFERENCES clients(id),
    property_id TEXT REFERENCES properties(id),
    match_score INTEGER,
    match_reasons TEXT[],
    broker_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_properties_district ON properties(district);
CREATE INDEX IF NOT EXISTS idx_properties_price ON properties(price_usd);
CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(status);
CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);
CREATE INDEX IF NOT EXISTS idx_appointments_broker_date ON appointments(broker_id, start_time);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);

-- Insert realistic Lima sample data (scrape-enhanced)
INSERT INTO properties (id, address, district, price_usd, sqm, bedrooms, bathrooms, type, status, features, location) VALUES
('PROP-2847', 'Jr. Las Lomas 432, Miraflores', 'Miraflores', 185000, 85, 2, 2, 'apartment', 'available', '["gym", "pool", "security"]', ST_SetSRID(ST_MakePoint(-77.0293, -12.1219), 4326)),
('PROP-2911', 'Av. Larco 780, Miraflores', 'Miraflores', 210000, 95, 3, 2, 'apartment', 'available', '["ocean_view", "parking"]', ST_SetSRID(ST_MakePoint(-77.0310, -12.1230), 4326)),
('PROP-3022', 'Calle Las Flores 120, San Borja', 'San Borja', 165000, 78, 2, 2, 'apartment', 'available', '["garden", "pet_friendly"]', ST_SetSRID(ST_MakePoint(-77.0076, -12.1004), 4326)),
('PROP-3155', 'Av. Circunvalación 450, Surco', 'Surco', 195000, 110, 3, 2, 'house', 'available', '["backyard", "garage"]', ST_SetSRID(ST_MakePoint(-76.9716, -12.1388), 4326)),
('PROP-3201', 'Av. Primavera 200, La Molina', 'La Molina', 320000, 150, 4, 3, 'house', 'available', '["pool", "security", "gated"]', ST_SetSRID(ST_MakePoint(-76.9365, -12.0727), 4326)),
('PROP-3320', 'Av. Pardo 650, Miraflores', 'Miraflores', 245000, 105, 3, 2, 'apartment', 'available', '["ocean_view", "gym", "parking"]', ST_SetSRID(ST_MakePoint(-77.0350, -12.1250), 4326)),
('PROP-3388', 'Calle Bolognesi 320, Barranco', 'Barranco', 175000, 80, 2, 2, 'apartment', 'available', '["heritage_building", "rooftop"]', ST_SetSRID(ST_MakePoint(-77.0215, -12.1435), 4326)),
('PROP-3450', 'Av. Javier Prado 1800, San Isidro', 'San Isidro', 280000, 120, 3, 3, 'apartment', 'available', '["concierge", "gym", "pool"]', ST_SetSRID(ST_MakePoint(-77.0300, -12.0980), 4326)),
('PROP-3512', 'Calle Los Pinos 88, Surco', 'Surco', 155000, 72, 2, 1, 'apartment', 'available', '["quiet_zone", "pet_friendly"]', ST_SetSRID(ST_MakePoint(-76.9750, -12.1350), 4326)),
('PROP-3600', 'Av. El Derby 450, Santiago de Surco', 'Surco', 420000, 200, 4, 4, 'house', 'available', '["pool", "garden", "gated", "security"]', ST_SetSRID(ST_MakePoint(-76.9650, -12.1050), 4326)),
('PROP-3701', 'Calle Grimaldo del Solar 180, Miraflores', 'Miraflores', 275000, 98, 3, 2, 'apartment', 'available', '["ocean_view", "gym", "concierge"]', ST_SetSRID(ST_MakePoint(-77.0320, -12.1240), 4326)),
('PROP-3802', 'Av. Dos de Mayo 800, San Isidro', 'San Isidro', 310000, 115, 3, 3, 'apartment', 'available', '["gym", "pool", "security", "parking"]', ST_SetSRID(ST_MakePoint(-77.0280, -12.0950), 4326)),
('PROP-3903', 'Calle Juan Fanning 250, Miraflores', 'Miraflores', 195000, 88, 2, 2, 'apartment', 'available', '["quiet_street", "pet_friendly", "storage"]', ST_SetSRID(ST_MakePoint(-77.0260, -12.1190), 4326)),
('PROP-4004', 'Av. Benavides 3200, Surco', 'Surco', 168000, 82, 2, 2, 'apartment', 'available', '["gym", "rooftop", "parking"]', ST_SetSRID(ST_MakePoint(-76.9700, -12.1300), 4326))
ON CONFLICT (id) DO NOTHING;

-- Sample clients
INSERT INTO clients (id, name, phone, email, budget_usd, preferred_districts, property_type, financing_status, financing_score, documents_status, status) VALUES
('CLI-1001', 'María González', '51999123456', 'maria.g@email.com', 180000, ARRAY['Miraflores', 'San Borja'], 'apartment', 'pre_approved', 82, '{"dni": true, "pay_stubs": true, "tax_returns": true, "pre_approval": true}', 'qualified'),
('CLI-1002', 'Carlos Rodríguez', '51999876543', 'carlos.r@email.com', 220000, ARRAY['Miraflores', 'San Isidro'], 'apartment', 'pending', 55, '{"dni": true, "pay_stubs": true, "tax_returns": false, "pre_approval": false}', 'needs_docs'),
('CLI-1003', 'Ana Lucero', '51999445566', 'ana.l@email.com', 160000, ARRAY['Surco', 'San Borja'], 'apartment', 'cash', 90, '{"dni": true, "pay_stubs": true, "tax_returns": true, "pre_approval": false}', 'qualified'),
('CLI-1004', 'Pedro Mendoza', '51999332211', 'pedro.m@email.com', 300000, ARRAY['La Molina', 'Surco'], 'house', 'pending', 45, '{"dni": true, "pay_stubs": false, "tax_returns": false, "pre_approval": false}', 'needs_docs'),
('CLI-1005', 'Laura Torres', '51999778899', 'laura.t@email.com', 190000, ARRAY['Barranco', 'Miraflores'], 'apartment', 'pre_approved', 75, '{"dni": true, "pay_stubs": true, "tax_returns": true, "pre_approval": true}', 'qualified')
ON CONFLICT (id) DO NOTHING;

-- Sample appointments for today (dynamic)
INSERT INTO appointments (id, broker_id, client_id, property_id, start_time, end_time, appointment_type, status, address, location) VALUES
('APT-001', 'broker_demo_001', 'CLI-1001', 'PROP-3022', NOW() + INTERVAL '2 hours', NOW() + INTERVAL '2 hours 45 minutes', 'showing', 'confirmed', 'Calle Las Flores 120, San Borja', ST_SetSRID(ST_MakePoint(-77.0076, -12.1004), 4326)),
('APT-002', 'broker_demo_001', 'CLI-1002', 'PROP-2847', NOW() + INTERVAL '4 hours', NOW() + INTERVAL '4 hours 45 minutes', 'showing', 'confirmed', 'Jr. Las Lomas 432, Miraflores', ST_SetSRID(ST_MakePoint(-77.0293, -12.1219), 4326)),
('APT-003', 'broker_demo_001', 'CLI-1003', 'PROP-3155', NOW() + INTERVAL '6 hours', NOW() + INTERVAL '6 hours 45 minutes', 'showing', 'tentative', 'Av. Circunvalación 450, Surco', ST_SetSRID(ST_MakePoint(-76.9716, -12.1388), 4326))
ON CONFLICT (id) DO NOTHING;
