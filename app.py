from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import sqlite3
from contextlib import contextmanager
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'


# Database connection helper
@contextmanager
def get_db_connection():
    conn = sqlite3.connect('data.db')
    conn.row_factory = sqlite3.Row  # This enables column access by name
    try:
        yield conn
    finally:
        conn.close()


def get_client_columns():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(Clients)')
        return [col[1] for col in cursor.fetchall()]


def generate_policy_number_v2(product_id, product_name):
    """Generate policy number using product ID for consistency"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get product abbreviation (you might want to store this in Products table)
        product_abbreviations = {
            1: 'INC',  # INCENDIE
            2: 'AUT',  # AUTOMOBILE
            3: 'MAL',  # MALADIE
            4: 'VOY',  # VOYAGE
            5: 'HAB'  # HABITATION
        }

        prefix = product_abbreviations.get(product_id, 'POL')
        current_year = datetime.now().year
        cursor.execute('''
                    SELECT PolicyNumber FROM Policies 
                    WHERE PolicyNumber LIKE ? 
                    ORDER BY PolicyID DESC LIMIT 1
                ''', (f'{prefix}{current_year}-%',))

        last_policy = cursor.fetchone()

        if last_policy:
            last_number = int(last_policy['PolicyNumber'].split('-')[1])
            next_number = last_number + 1
        else:
            next_number = 1

        return f'{prefix}{current_year}-{next_number}'


def get_parameter_form_data():
    """Get all dropdown options for policy parameters form"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM Provinces ORDER BY ProvinceName')
        provinces = cursor.fetchall()

        cursor.execute('SELECT * FROM TypeBien ORDER BY TypeBienName')
        type_bien = cursor.fetchall()

        cursor.execute('SELECT * FROM SousTypeBien ORDER BY SousTypeBienName')
        sous_type_bien = cursor.fetchall()

        cursor.execute('SELECT * FROM CategorieBien ORDER BY CategorieBienName')
        categorie_bien = cursor.fetchall()

        cursor.execute('SELECT * FROM TypeMateriaux ORDER BY TypeMateriauxName')
        type_materiaux = cursor.fetchall()

        cursor.execute('SELECT * FROM CategorieRisque ORDER BY CategorieRisqueName')
        categorie_risque = cursor.fetchall()

        cursor.execute('SELECT * FROM Garantits ORDER BY GarantitID')
        garantits = cursor.fetchall()

    return {
        'provinces': provinces,
        'type_bien': type_bien,
        'sous_type_bien': sous_type_bien,
        'categorie_bien': categorie_bien,
        'type_materiaux': type_materiaux,
        'categorie_risque': categorie_risque,
        'garantits': garantits
    }


def get_sous_types_by_parent(parent_id):
    """Get sub-types for a given parent type"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM SousTypeBien WHERE ParentID = ? ORDER BY SousTypeBienName', (parent_id,))
        return cursor.fetchall()


def calculate_prime(policy_id):
    """Calculate the insurance prime for a policy using SQLite"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Calculate prime using SQL with detailed breakdown
        cursor.execute('''
            SELECT 
                pp.ParamID,
                pp.SousTypeBienID,
                stb.SousTypeBienName,
                pp.ValeurBienAssure,
                pp.ValeurEquipementsInterieur,
                (pp.ValeurBienAssure + pp.ValeurEquipementsInterieur) AS ValeurAssure,
                GROUP_CONCAT(g.GarantitCode) AS SelectedGarantits,
                SUM(t.TarifRate) AS TotalTarifRate,

                -- Prime Nette (PN)
                SUM((pp.ValeurBienAssure + pp.ValeurEquipementsInterieur) * t.TarifRate / 100) AS PN,

                -- Frais (FR) = 8% of PN
                SUM((pp.ValeurBienAssure + pp.ValeurEquipementsInterieur) * t.TarifRate / 100) * 0.08 AS FR,

                -- Commission de Courtage (CD) = 5.5% of (PN + FR)
                (SUM((pp.ValeurBienAssure + pp.ValeurEquipementsInterieur) * t.TarifRate / 100) * 1.08) * 0.055 AS CD,

                -- TVA = 18% of (PN + FR + CD)
                (SUM((pp.ValeurBienAssure + pp.ValeurEquipementsInterieur) * t.TarifRate / 100) * 1.08 * 1.055) * 0.18 AS TVA,

                -- Prime Totale (PT) = PN + FR + CD + TVA
                SUM((pp.ValeurBienAssure + pp.ValeurEquipementsInterieur) * t.TarifRate / 100) * 1.08 * 1.055 * 1.18 AS PT,

                -- Detailed breakdown for each garantit with all components
                GROUP_CONCAT(
                    g.GarantitCode || ':' || 
                    t.TarifRate || ':' || 
                    ((pp.ValeurBienAssure + pp.ValeurEquipementsInterieur) * t.TarifRate / 100) || ':' ||  -- PN
                    ((pp.ValeurBienAssure + pp.ValeurEquipementsInterieur) * t.TarifRate / 100) * 0.08 || ':' ||  -- FR
                    ((pp.ValeurBienAssure + pp.ValeurEquipementsInterieur) * t.TarifRate / 100) * 1.08 * 0.055 || ':' ||  -- CD
                    ((pp.ValeurBienAssure + pp.ValeurEquipementsInterieur) * t.TarifRate / 100) * 1.08 * 1.055 * 0.18 || ':' ||  -- TVA
                    ((pp.ValeurBienAssure + pp.ValeurEquipementsInterieur) * t.TarifRate / 100) * 1.08 * 1.055 * 1.18  -- PT
                ) AS GarantitDetails

            FROM PolicyParameters pp
            JOIN PolicyGarantits pg ON pp.ParamID = pg.PolicyParamID
            JOIN Garantits g ON pg.GarantitID = g.GarantitID
            JOIN Tarifs t ON pp.SousTypeBienID = t.SousTypeBienID AND pg.GarantitID = t.GarantitID
            JOIN SousTypeBien stb ON pp.SousTypeBienID = stb.SousTypeBienID
            WHERE pp.PolicyID = ? AND pg.IsSelected = 1
            GROUP BY pp.ParamID
        ''', (policy_id,))

        prime_data = cursor.fetchone()

        if not prime_data:
            return None

        # Parse garantit details with all components
        garantit_details = []
        if prime_data['GarantitDetails']:
            for detail in prime_data['GarantitDetails'].split(','):
                parts = detail.split(':')
                if len(parts) == 7:
                    garantit_details.append({
                        'code': parts[0],
                        'tarif_rate': float(parts[1]),
                        'pn': float(parts[2]),  # Prime Nette
                        'fr': float(parts[3]),  # Frais
                        'cd': float(parts[4]),  # Commission de Courtage
                        'tva': float(parts[5]),  # TVA
                        'pt': float(parts[6])  # Prime Totale
                    })

        return {
            'param_id': prime_data['ParamID'],
            'sous_type_bien_id': prime_data['SousTypeBienID'],
            'sous_type_bien_name': prime_data['SousTypeBienName'],
            'valeur_bien': prime_data['ValeurBienAssure'] or 0,
            'valeur_equipements': prime_data['ValeurEquipementsInterieur'] or 0,
            'valeur_assure': prime_data['ValeurAssure'] or 0,
            'selected_garantits': prime_data['SelectedGarantits'],
            'total_tarif_rate': prime_data['TotalTarifRate'] or 0,
            'pn': prime_data['PN'] or 0,
            'fr': prime_data['FR'] or 0,
            'cd': prime_data['CD'] or 0,
            'tva': prime_data['TVA'] or 0,
            'pt': prime_data['PT'] or 0,
            'garantit_details': garantit_details
        }


@app.route('/')
def dashboard():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get total clients count
        cursor.execute('SELECT COUNT(*) FROM Clients')
        total_clients = cursor.fetchone()[0]

        # Get recent clients
        cursor.execute('SELECT * FROM Clients ORDER BY ID DESC LIMIT 5')
        recent_clients = cursor.fetchall()

        # Get columns for system info
        columns = get_client_columns()

    return render_template('index.html',
                           total_clients=total_clients,
                           recent_clients=recent_clients,
                           columns=columns)


@app.route('/clients')
def clients():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get clients for current page
        cursor.execute('SELECT * FROM Clients ORDER BY ID LIMIT ? OFFSET ?', (per_page, offset))
        clients = cursor.fetchall()

        # Get total count for pagination
        cursor.execute('SELECT COUNT(*) FROM Clients')
        total_clients = cursor.fetchone()[0]

    total_pages = (total_clients + per_page - 1) // per_page

    return render_template('clients.html',
                           clients=clients,
                           page=page,
                           total_pages=total_pages,
                           total_clients=total_clients)


@app.route('/client/<int:id>')
def view_client(id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Clients WHERE ID = ?', (id,))
        client = cursor.fetchone()

    if not client:
        flash('Client not found!', 'danger')
        return redirect(url_for('clients'))

    columns = get_client_columns()
    return render_template('client_view.html', client=client, columns=columns)


@app.route('/client/add', methods=['GET', 'POST'])
def add_client():
    columns = get_client_columns()

    if request.method == 'POST':
        try:
            # Get form data and build SQL query dynamically
            field_names = []
            field_values = []
            placeholders = []

            for column in columns:
                if column != 'ID':  # Skip auto-increment ID
                    value = request.form.get(column)
                    if value is not None and value != '':
                        field_names.append(column)
                        field_values.append(value)
                        placeholders.append('?')

            if field_names:
                sql = f"INSERT INTO Clients ({', '.join(field_names)}) VALUES ({', '.join(placeholders)})"

                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, field_values)
                    conn.commit()

                flash('Client added successfully!', 'success')
                return redirect(url_for('clients'))
            else:
                flash('No data provided!', 'warning')

        except Exception as e:
            flash(f'Error adding client: {str(e)}', 'danger')

    return render_template('client_form.html', client=None, columns=columns, action='add')


@app.route('/client/edit/<int:id>', methods=['GET', 'POST'])
def edit_client(id):
    columns = get_client_columns()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Clients WHERE ID = ?', (id,))
        client = cursor.fetchone()

    if not client:
        flash('Client not found!', 'danger')
        return redirect(url_for('clients'))

    if request.method == 'POST':
        try:
            # Build update query dynamically
            updates = []
            values = []

            for column in columns:
                if column != 'ID':  # Don't update ID
                    value = request.form.get(column)
                    updates.append(f"{column} = ?")
                    values.append(value)

            values.append(id)  # For WHERE clause

            sql = f"UPDATE Clients SET {', '.join(updates)} WHERE ID = ?"

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, values)
                conn.commit()

            flash('Client updated successfully!', 'success')
            return redirect(url_for('view_client', id=id))

        except Exception as e:
            flash(f'Error updating client: {str(e)}', 'danger')

    return render_template('client_form.html', client=dict(client), columns=columns, action='edit')


@app.route('/client/delete/<int:id>', methods=['POST'])
def delete_client(id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM Clients WHERE ID = ?', (id,))
            conn.commit()

        flash('Client deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting client: {str(e)}', 'danger')

    return redirect(url_for('clients'))


@app.route('/api/clients')
def api_clients():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Clients')
        clients = cursor.fetchall()

    return jsonify([dict(client) for client in clients])


# Add this route to your existing app.py
@app.route('/search', methods=['GET', 'POST'])
def search_clients():
    search_query = request.args.get('q', '') or request.form.get('search_query', '')
    search_type = request.args.get('type', 'all') or request.form.get('search_type', 'all')

    if not search_query:
        return redirect(url_for('clients'))

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Build search query based on search type
        if search_type == 'id':
            try:
                search_id = int(search_query)
                cursor.execute('SELECT * FROM Clients WHERE ID = ?', (search_id,))
            except ValueError:
                cursor.execute('SELECT * FROM Clients WHERE ID = 0')  # Return empty if not numeric
        elif search_type == 'nom':
            cursor.execute('SELECT * FROM Clients WHERE Nom LIKE ?', (f'%{search_query}%',))
        elif search_type == 'prenom':
            cursor.execute('SELECT * FROM Clients WHERE Prenom LIKE ?', (f'%{search_query}%',))
        elif search_type == 'mobphone':
            cursor.execute('SELECT * FROM Clients WHERE MobPhone LIKE ? OR MobPhone2 LIKE ?',
                           (f'%{search_query}%', f'%{search_query}%'))
        else:  # search all fields
            cursor.execute('''
                SELECT * FROM Clients 
                WHERE ID LIKE ? OR Nom LIKE ? OR Prenom LIKE ? OR MobPhone LIKE ? OR MobPhone2 LIKE ?
                OR Email LIKE ? OR NIF LIKE ? OR Residence LIKE ?
            ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%',
                  f'%{search_query}%', f'%{search_query}%', f'%{search_query}%',
                  f'%{search_query}%', f'%{search_query}%'))

        clients = cursor.fetchall()
        total_results = len(clients)

    return render_template('search_results.html',
                           clients=clients,
                           search_query=search_query,
                           search_type=search_type,
                           total_results=total_results)


# Policy Management Routes
def get_policy_form_data():
    """Get all dropdown options for policy form"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM Products')
        products = cursor.fetchall()

        cursor.execute('SELECT * FROM PolicyTypes')
        policy_types = cursor.fetchall()

        cursor.execute('SELECT * FROM PolicyOptions')
        options = cursor.fetchall()

        cursor.execute('SELECT * FROM Agencies')
        agencies = cursor.fetchall()

        cursor.execute('SELECT * FROM Users WHERE IsActive = 1')
        users = cursor.fetchall()

        cursor.execute('SELECT * FROM EventTypes')
        event_types = cursor.fetchall()

        cursor.execute('SELECT * FROM Terms')
        terms = cursor.fetchall()

        cursor.execute('SELECT * FROM Courtiers WHERE IsActive = 1 ORDER BY CourtierName')
        courtiers = cursor.fetchall()

    return {
        'products': products,
        'policy_types': policy_types,
        'options': options,
        'agencies': agencies,
        'users': users,
        'event_types': event_types,
        'terms': terms,
        'courtiers': courtiers
    }


@app.route('/client/<int:client_id>/policies')
def client_policies(client_id):
    """View all policies for a specific client"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get client info
        cursor.execute('SELECT * FROM Clients WHERE ID = ?', (client_id,))
        client = cursor.fetchone()

        # Get client's policies with joined data including courtier
        cursor.execute('''
            SELECT p.*, pr.ProductName, pt.TypeName as PolicyTypeName, 
                   po.OptionName, a.AgencyName, u.FullName as CreatedByName,
                   et.EventName, t.TermName, c.CourtierName
            FROM Policies p
            JOIN Products pr ON p.ProductID = pr.ProductID
            JOIN PolicyTypes pt ON p.PolicyTypeID = pt.TypeID
            JOIN PolicyOptions po ON p.OptionID = po.OptionID
            JOIN Agencies a ON p.AgencyID = a.AgencyID
            JOIN Users u ON p.CreatedByUserID = u.UserID
            JOIN EventTypes et ON p.EventTypeID = et.EventTypeID
            JOIN Terms t ON p.TermID = t.TermID
            LEFT JOIN Courtiers c ON p.CourtierID = c.CourtierID
            WHERE p.ClientID = ? 
            ORDER BY p.CreatedOn DESC
        ''', (client_id,))
        policies = cursor.fetchall()

    if not client:
        flash('Client not found!', 'danger')
        return redirect(url_for('clients'))

    return render_template('client_policies.html', client=client, policies=policies)


@app.route('/client/<int:client_id>/policy/add', methods=['GET', 'POST'])
def add_policy(client_id):
    """Add a new policy for a client"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Clients WHERE ID = ?', (client_id,))
        client = cursor.fetchone()

    if not client:
        flash('Client not found!', 'danger')
        return redirect(url_for('clients'))

    form_data = get_policy_form_data()

    if request.method == 'POST':
        try:
            product_id = int(request.form['ProductID'])

            # Get product name for policy number generation
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT ProductName FROM Products WHERE ProductID = ?', (product_id,))
                product = cursor.fetchone()

            if not product:
                flash('Invalid product selected!', 'danger')
                return redirect(url_for('add_policy', client_id=client_id))

            # Generate automatic policy number
            policy_number = generate_policy_number_v2(product_id, product['ProductName'])

            policy_data = (
                product_id,
                policy_number,  # Use auto-generated number
                request.form.get('OldPolicyNumber', ''),
                request.form.get('EndorsementNumber', ''),
                request.form.get('OtherEndorsementNumber', '00000'),
                client_id,
                int(request.form['EventTypeID']),
                int(request.form['PolicyTypeID']),
                int(request.form['OptionID']),
                request.form['Description'],
                int(request.form['CourtierID']),
                int(request.form['TermID']),
                request.form['ProductionDate'],
                request.form.get('DurationMonths'),
                request.form['ExpiryDate'],
                request.form.get('PurchaseOrder', ''),
                request.form.get('PurchaseOrderNumber', ''),
                request.form.get('CreditAuthorizedBy', '---'),
                int(request.form['AgencyID']),
                int(request.form['CreatedByUserID']),
                request.form['CreatedOn']
            )

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO Policies 
                    (ProductID, PolicyNumber, OldPolicyNumber, EndorsementNumber, 
                     OtherEndorsementNumber, ClientID, EventTypeID, PolicyTypeID, 
                     OptionID, Description, CourtierID, TermID, ProductionDate, 
                     DurationMonths, ExpiryDate, PurchaseOrder, PurchaseOrderNumber, 
                     CreditAuthorizedBy, AgencyID, CreatedByUserID, CreatedOn)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', policy_data)
                conn.commit()

            # Get the new policy ID for redirect
            new_policy_id = cursor.lastrowid
            flash(f'Policy {policy_number} added successfully!', 'success')
            return redirect(url_for('view_policy', policy_id=new_policy_id))

        except Exception as e:
            flash(f'Error adding policy: {str(e)}', 'danger')

    return render_template('policy_form.html',
                           client=client,
                           policy=None,
                           action='add',
                           form_data=form_data)


@app.route('/policy/<int:policy_id>/edit', methods=['GET', 'POST'])
def edit_policy(policy_id):
    """Edit an existing policy"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, c.Nom, c.Prenom 
            FROM Policies p 
            JOIN Clients c ON p.ClientID = c.ID 
            WHERE p.PolicyID = ?
        ''', (policy_id,))
        policy_info = cursor.fetchone()

    if not policy_info:
        flash('Policy not found!', 'danger')
        return redirect(url_for('clients'))

    form_data = get_policy_form_data()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Courtiers WHERE IsActive = 1')
        courtiers = cursor.fetchall()
    form_data['courtiers'] = courtiers

    if request.method == 'POST':
        try:
            policy_data = (
                int(request.form['ProductID']),
                request.form.get('PolicyNumber', ''),  # Keep original number for edits
                request.form.get('OldPolicyNumber', ''),
                request.form.get('EndorsementNumber', ''),
                request.form.get('OtherEndorsementNumber', '00000'),
                int(request.form['EventTypeID']),
                int(request.form['PolicyTypeID']),
                int(request.form['OptionID']),
                request.form['Description'],
                int(request.form['CourtierID']),
                int(request.form['TermID']),
                request.form['ProductionDate'],
                request.form.get('DurationMonths'),
                request.form['ExpiryDate'],
                request.form.get('PurchaseOrder', ''),
                request.form.get('PurchaseOrderNumber', ''),
                request.form.get('CreditAuthorizedBy', '---'),
                int(request.form['AgencyID']),
                policy_id
            )

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE Policies SET 
                    ProductID = ?, PolicyNumber = ?, OldPolicyNumber = ?, EndorsementNumber = ?,
                    OtherEndorsementNumber = ?, EventTypeID = ?, PolicyTypeID = ?, 
                    OptionID = ?, Description = ?, CourtierID = ?, TermID = ?, ProductionDate = ?, 
                    DurationMonths = ?, ExpiryDate = ?, PurchaseOrder = ?, PurchaseOrderNumber = ?, 
                    CreditAuthorizedBy = ?, AgencyID = ?, UpdatedOn = CURRENT_TIMESTAMP
                    WHERE PolicyID = ?
                ''', policy_data)
                conn.commit()

            flash('Policy updated successfully!', 'success')
            return redirect(url_for('client_policies', client_id=policy_info['ClientID']))

        except Exception as e:
            flash(f'Error updating policy: {str(e)}', 'danger')

    return render_template('policy_form.html',
                           client=policy_info,
                           policy=dict(policy_info),
                           action='edit',
                           form_data=form_data)


@app.route('/policy/<int:policy_id>/delete', methods=['POST'])
def delete_policy(policy_id):
    """Delete a policy"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Get client ID before deletion for redirect
            cursor.execute('SELECT ClientID FROM Policies WHERE PolicyID = ?', (policy_id,))
            policy = cursor.fetchone()

            if policy:
                cursor.execute('DELETE FROM Policies WHERE PolicyID = ?', (policy_id,))
                conn.commit()
                flash('Policy deleted successfully!', 'success')
                return redirect(url_for('client_policies', client_id=policy['ClientID']))
            else:
                flash('Policy not found!', 'danger')
                return redirect(url_for('clients'))

    except Exception as e:
        flash(f'Error deleting policy: {str(e)}', 'danger')
        return redirect(url_for('clients'))


@app.route('/policies')
def all_policies():
    """View all policies across all clients"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get policies with client info
        cursor.execute('''
            SELECT p.*, c.Nom, c.Prenom, c.NIF, pr.ProductName, 
                   pt.TypeName as PolicyTypeName, a.AgencyName
            FROM Policies p 
            JOIN Clients c ON p.ClientID = c.ID 
            JOIN Products pr ON p.ProductID = pr.ProductID
            JOIN PolicyTypes pt ON p.PolicyTypeID = pt.TypeID
            JOIN Agencies a ON p.AgencyID = a.AgencyID
            ORDER BY p.CreatedOn DESC 
            LIMIT ? OFFSET ?
        ''', (per_page, offset))
        policies = cursor.fetchall()

        # Get total count
        cursor.execute('SELECT COUNT(*) FROM Policies')
        total_policies = cursor.fetchone()[0]

    total_pages = (total_policies + per_page - 1) // per_page

    return render_template('all_policies.html',
                           policies=policies,
                           page=page,
                           total_pages=total_pages,
                           total_policies=total_policies)


@app.route('/policy/<int:policy_id>')
def view_policy(policy_id):
    """View detailed policy information"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get policy details with all joined information
        cursor.execute('''
            SELECT p.*, pr.ProductName, pt.TypeName as PolicyTypeName, 
                   po.OptionName, a.AgencyName, u.FullName as CreatedByName,
                   et.EventName, t.TermName, c.CourtierName,
                   cl.Nom, cl.Prenom, cl.NIF, cl.ID as ClientID
            FROM Policies p
            JOIN Products pr ON p.ProductID = pr.ProductID
            JOIN PolicyTypes pt ON p.PolicyTypeID = pt.TypeID
            JOIN PolicyOptions po ON p.OptionID = po.OptionID
            JOIN Agencies a ON p.AgencyID = a.AgencyID
            JOIN Users u ON p.CreatedByUserID = u.UserID
            JOIN EventTypes et ON p.EventTypeID = et.EventTypeID
            JOIN Terms t ON p.TermID = t.TermID
            LEFT JOIN Courtiers c ON p.CourtierID = c.CourtierID
            JOIN Clients cl ON p.ClientID = cl.ID
            WHERE p.PolicyID = ?
        ''', (policy_id,))
        policy = cursor.fetchone()

    if not policy:
        flash('Policy not found!', 'danger')
        return redirect(url_for('clients'))

    return render_template('policy_view.html', policy=policy, client=policy)


@app.route('/policy/<int:policy_id>/parameters')
def policy_parameters(policy_id):
    """View policy parameters"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get policy info
        cursor.execute('''
            SELECT p.*, pr.ProductName, cl.Nom, cl.Prenom 
            FROM Policies p
            JOIN Products pr ON p.ProductID = pr.ProductID
            JOIN Clients cl ON p.ClientID = cl.ID
            WHERE p.PolicyID = ?
        ''', (policy_id,))
        policy = cursor.fetchone()

        # Get parameters if they exist
        cursor.execute('''
            SELECT pp.*, pv.ProvinceName, tb.TypeBienName, stb.SousTypeBienName,
                   cb.CategorieBienName, tm.TypeMateriauxName, cr.CategorieRisqueName
            FROM PolicyParameters pp
            LEFT JOIN Provinces pv ON pp.ProvinceID = pv.ProvinceID
            LEFT JOIN TypeBien tb ON pp.TypeBienID = tb.TypeBienID
            LEFT JOIN SousTypeBien stb ON pp.SousTypeBienID = stb.SousTypeBienID
            LEFT JOIN CategorieBien cb ON pp.CategorieBienID = cb.CategorieBienID
            LEFT JOIN TypeMateriaux tm ON pp.TypeMateriauxID = tm.TypeMateriauxID
            LEFT JOIN CategorieRisque cr ON pp.CategorieRisqueID = cr.CategorieRisqueID
            WHERE pp.PolicyID = ?
        ''', (policy_id,))
        parameters = cursor.fetchone()

        # Get Garantits for this policy if parameters exist
        garantits = []
        if parameters:
            cursor.execute('''
                SELECT g.*, pg.IsSelected
                FROM Garantits g
                LEFT JOIN PolicyGarantits pg ON g.GarantitID = pg.GarantitID AND pg.PolicyParamID = ?
                ORDER BY g.GarantitID
            ''', (parameters['ParamID'],))
            garantits = cursor.fetchall()

    if not policy:
        flash('Policy not found!', 'danger')
        return redirect(url_for('clients'))

    # Check if this is an INCENDIE policy
    if policy['ProductName'] != 'INCENDIE':
        flash('Parameters are only available for INCENDIE policies', 'warning')
        return redirect(url_for('view_policy', policy_id=policy_id))

    form_data = get_parameter_form_data()

    return render_template('policy_parameters.html',
                           policy=policy,
                           parameters=parameters,
                           garantits=garantits,
                           form_data=form_data)


@app.route('/policy/<int:policy_id>/parameters/edit', methods=['GET', 'POST'])
def edit_policy_parameters(policy_id):
    """Edit policy parameters"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get policy info
        cursor.execute('''
            SELECT p.*, pr.ProductName 
            FROM Policies p
            JOIN Products pr ON p.ProductID = pr.ProductID
            WHERE p.PolicyID = ?
        ''', (policy_id,))
        policy = cursor.fetchone()

        # Get existing parameters if any
        cursor.execute('SELECT * FROM PolicyParameters WHERE PolicyID = ?', (policy_id,))
        existing_params = cursor.fetchone()

        # Get Garantits selection if parameters exist
        garantits_selection = {}
        if existing_params:
            cursor.execute('''
                SELECT GarantitID, IsSelected 
                FROM PolicyGarantits 
                WHERE PolicyParamID = ?
            ''', (existing_params['ParamID'],))
            for row in cursor.fetchall():
                garantits_selection[row['GarantitID']] = row['IsSelected']

    if not policy:
        flash('Policy not found!', 'danger')
        return redirect(url_for('clients'))

    # Check if this is an INCENDIE policy
    if policy['ProductName'] != 'INCENDIE':
        flash('Parameters are only available for INCENDIE policies', 'warning')
        return redirect(url_for('view_policy', policy_id=policy_id))

    form_data = get_parameter_form_data()

    if request.method == 'POST':
        try:
            param_data = (
                request.form.get('BienAsCode'),
                request.form.get('CompteSouscripteur'),
                request.form.get('Description'),
                int(request.form['ProvinceID']) if request.form.get('ProvinceID') else None,
                request.form.get('Ville'),
                request.form.get('Zone'),
                request.form.get('AdresseResidence'),
                int(request.form['TypeBienID']) if request.form.get('TypeBienID') else None,
                int(request.form['SousTypeBienID']) if request.form.get('SousTypeBienID') else None,
                int(request.form['CategorieBienID']) if request.form.get('CategorieBienID') else None,
                int(request.form['TypeMateriauxID']) if request.form.get('TypeMateriauxID') else None,
                int(request.form['CategorieRisqueID']) if request.form.get('CategorieRisqueID') else None,
                float(request.form.get('ValeurBienAssure', 0)),
                float(request.form.get('ValeurEquipementsInterieur', 0)),
                request.form.get('Observations'),
                policy_id
            )

            with get_db_connection() as conn:
                cursor = conn.cursor()

                if existing_params:
                    # Update existing parameters
                    cursor.execute('''
                        UPDATE PolicyParameters SET 
                        BienAsCode = ?, CompteSouscripteur = ?, Description = ?, 
                        ProvinceID = ?, Ville = ?, Zone = ?, AdresseResidence = ?,
                        TypeBienID = ?, SousTypeBienID = ?, CategorieBienID = ?,
                        TypeMateriauxID = ?, CategorieRisqueID = ?,
                        ValeurBienAssure = ?, ValeurEquipementsInterieur = ?,
                        Observations = ?, UpdatedAt = CURRENT_TIMESTAMP
                        WHERE PolicyID = ?
                    ''', param_data)
                    param_id = existing_params['ParamID']
                else:
                    # Insert new parameters
                    cursor.execute('''
                        INSERT INTO PolicyParameters 
                        (BienAsCode, CompteSouscripteur, Description, ProvinceID, Ville, Zone,
                         AdresseResidence, TypeBienID, SousTypeBienID, CategorieBienID,
                         TypeMateriauxID, CategorieRisqueID, ValeurBienAssure,
                         ValeurEquipementsInterieur, Observations, PolicyID)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', param_data)
                    param_id = cursor.lastrowid

                # Handle Garantits selection
                cursor.execute('DELETE FROM PolicyGarantits WHERE PolicyParamID = ?', (param_id,))

                for garantit in form_data['garantits']:
                    is_selected = 1 if request.form.get(f'garantit_{garantit["GarantitID"]}') == 'on' else 0
                    cursor.execute('''
                        INSERT INTO PolicyGarantits (PolicyParamID, GarantitID, IsSelected)
                        VALUES (?, ?, ?)
                    ''', (param_id, garantit['GarantitID'], is_selected))

                conn.commit()

            flash('Policy parameters saved successfully!', 'success')
            return redirect(url_for('policy_parameters', policy_id=policy_id))

        except Exception as e:
            flash(f'Error saving parameters: {str(e)}', 'danger')

    return render_template('policy_parameters_form.html',
                           policy=policy,
                           parameters=dict(existing_params) if existing_params else None,
                           garantits_selection=garantits_selection,
                           form_data=form_data)


@app.route('/api/sous-types/<int:parent_id>')
def get_sous_types_api(parent_id):
    """API endpoint to get sub-types for a parent type"""
    sous_types = get_sous_types_by_parent(parent_id)
    return jsonify([dict(st) for st in sous_types])

@app.template_filter('format_currency')
def format_currency(value):
    """Format number as currency in BIF"""
    if value is None:
        return '---'
    try:
        # Format as BIF (Burundian Franc) with comma separation
        return f"{float(value):,.0f} BIF"
    except (ValueError, TypeError):
        return '---'


@app.route('/policy/<int:policy_id>/calculate-prime')
def calculate_policy_prime(policy_id):
    """Calculate and display insurance prime"""
    prime_result = calculate_prime(policy_id)

    if not prime_result:
        flash('Cannot calculate prime: Missing policy parameters or garantits', 'warning')
        return redirect(url_for('policy_parameters', policy_id=policy_id))

    # Store calculation in database
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Insert prime calculation
        cursor.execute('''
            INSERT INTO PrimeCalculations 
            (PolicyID, ParamID, SousTypeBienID, ValeurBienAssure, ValeurEquipementsInterieur, 
             ValeurAssure, TotalTarifRate, PN, FR, CD, TVA, PT)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            policy_id,
            prime_result['param_id'],
            prime_result['sous_type_bien_id'],
            prime_result['valeur_bien'],
            prime_result['valeur_equipements'],
            prime_result['valeur_assure'],
            prime_result['total_tarif_rate'],
            prime_result['pn'],
            prime_result['fr'],
            prime_result['cd'],
            prime_result['tva'],
            prime_result['pt']
        ))

        prime_id = cursor.lastrowid

        # Insert prime details for each garantit with all components
        for detail in prime_result['garantit_details']:
            cursor.execute('SELECT GarantitID FROM Garantits WHERE GarantitCode = ?', (detail['code'],))
            garantit = cursor.fetchone()

            if garantit:
                cursor.execute('''
                    INSERT INTO PrimeDetails 
                    (PrimeID, GarantitID, TarifRate, PrimeNette, Frais, CommissionCourtage, TVA, PrimeTotale)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    prime_id,
                    garantit['GarantitID'],
                    detail['tarif_rate'],
                    detail['pn'],
                    detail['fr'],
                    detail['cd'],
                    detail['tva'],
                    detail['pt']
                ))

        conn.commit()

    return render_template('prime_calculation.html',
                           policy_id=policy_id,
                           prime_result=prime_result)



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)