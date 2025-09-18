# Bicor Insurance CRM

A functional web-based CRM system developed during an internship for Bicor Insurance Company. This system manages client information, insurance policies, and automated prime calculations.

## 🚀 Features

### 👥 Client Management
- Create, view, edit, and delete client records
- Search clients by ID, name, phone number, or email
- Professional interface with client details display

### 📋 Policy Management
- **Multi-product support**: INCENDIE, AUTOMOBILE, MALADIE, VOYAGE, HABITATION
- **Automatic numbering**: Policies are auto-generated (e.g., INC2025-1)
- **CRUD operations**: Full Create, Read, Update, Delete functionality
- **Status tracking**: Active, Expired, Cancelled status management

### 🛡️ INCENDIE Policy Parameters
- Detailed property information forms
- Coverage selection (Garantits) with IEFCACV as default
- Property type classification (Type Bien, Sous Type Bien)
- Risk assessment and material types
- Location data with province/region support

### 🧮 Automated Prime Calculation
- **Intelligent calculation system**: 
  - Prime Nette (PN) = Value × Tarif Rate
  - Frais (FR) = PN × 8%
  - Commission (CD) = (PN + FR) × 5.5%
  - TVA = (PN + FR + CD) × 18%
  - Prime Totale = PN + FR + CD + TVA
- **Tarif-based system**: Different rates per property type and coverage
- **Detailed breakdown**: Complete audit trail of calculations

## 🛠️ Tech Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **Frontend**: HTML5, Bootstrap 5, JavaScript
- **Styling**: Custom CSS with Bicor green theme

## 📦 Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt

2. Run the application:

bash
python app.py


🗄️ Database Includes
Clients and Policies tables

Parameter tables for INCENDIE policies

Tarif tables for prime calculations

Reference tables (Provinces, Garantits, Property types)

Prime calculation audit tables

🎯 Key Functionality
✅ Complete client CRM system

✅ Multi-product policy management

✅ Detailed parameter system for INCENDIE policies

✅ Coverage selection with Garantits

✅ Automated prime calculation with breakdown

✅ Professional insurance-themed UI

✅ Responsive design for all devices

📱 Interface
Modern, professional interface featuring:

Bicor's corporate green and white theme

Bootstrap-based responsive design

intuitive navigation and forms

Professional data presentation

Mobile-friendly layout

