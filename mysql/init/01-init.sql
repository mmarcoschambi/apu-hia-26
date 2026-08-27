-- ==============================================================================
-- SCHEMA INICIAL - PLATAFORMA PMAI DOCKER 2026 (HIA - UNJu)
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS pmai_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE pmai_db;

-- Tabla de productos / entidades para automatizaciones de prueba
CREATE TABLE IF NOT EXISTS productos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    categoria VARCHAR(100) NOT NULL,
    precio DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    stock INT NOT NULL DEFAULT 0,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de logs de eventos procesados por n8n
CREATE TABLE IF NOT EXISTS eventos_webhook (
    id INT AUTO_INCREMENT PRIMARY KEY,
    origen VARCHAR(100) NOT NULL,
    tipo_evento VARCHAR(100) NOT NULL,
    payload JSON NOT NULL,
    procesado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Inserción de registros iniciales de prueba (Seed Data)
INSERT INTO productos (codigo, nombre, categoria, precio, stock) VALUES
('PROD-001', 'Sensor IoT de Temperatura DHT22', 'Hardware', 14500.00, 50),
('PROD-002', 'Microcontrolador ESP32 DevKit V1', 'Hardware', 18900.00, 35),
('PROD-003', 'Módulo Relé 4 Canales 5V', 'Automatización', 8200.00, 80)
ON DUPLICATE KEY UPDATE nombre=VALUES(nombre);
