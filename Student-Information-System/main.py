
from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import csv
from io import StringIO

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
db = SQLAlchemy(app)

class MaintenanceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=False)
    performed_by = db.Column(db.String(100))

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    serial_number = db.Column(db.String(100))
    purchase_date = db.Column(db.DateTime)
    next_maintenance = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    purchase_price = db.Column(db.Float, default=0.0)
    annual_depreciation_rate = db.Column(db.Float, default=0.2)  # 20% per year
    maintenance_logs = db.relationship('MaintenanceLog', backref='item', lazy=True)

    @property
    def current_value(self):
        try:
            if not self.purchase_date or not self.purchase_price:
                return 0.0
            years = float((datetime.now() - self.purchase_date).days) / 365.25
            rate = float(self.annual_depreciation_rate) / 100  # Convert percentage to decimal
            depreciated_value = float(self.purchase_price) * pow((1 - rate), years)
            return max(0.0, float(depreciated_value))
        except Exception as e:
            return 0.0

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    search = request.args.get('search', '')
    category_filter = request.args.get('category_filter', '')
    status_filter = request.args.get('status_filter', '')
    
    query = Item.query
    
    if search:
        query = query.filter(
            (Item.name.contains(search)) |
            (Item.category.contains(search)) |
            (Item.status.contains(search)) |
            (Item.serial_number.contains(search))
        )
    
    if category_filter:
        query = query.filter(Item.category == category_filter)
    
    if status_filter:
        query = query.filter(Item.status == status_filter)
        
    items = query.all()

    # Get maintenance alerts
    today = datetime.now()
    maintenance_alerts = Item.query.filter(
        Item.next_maintenance <= today
    ).all()

    # Calculate financial metrics
    total_purchase_value = sum(item.purchase_price or 0 for item in items)
    total_current_value = sum(item.current_value for item in items)
    total_depreciation = total_purchase_value - total_current_value

    return render_template('index.html', 
                         items=items, 
                         search=search, 
                         maintenance_alerts=maintenance_alerts,
                         total_purchase_value=total_purchase_value,
                         total_current_value=total_current_value,
                         total_depreciation=total_depreciation)

@app.route('/export')
def export_csv():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Category', 'Status', 'Serial Number', 'Purchase Date', 'Next Maintenance', 'Notes'])

    items = Item.query.all()
    for item in items:
        writer.writerow([
            item.name,
            item.category,
            item.status,
            item.serial_number,
            item.purchase_date.strftime('%Y-%m-%d') if item.purchase_date else '',
            item.next_maintenance.strftime('%Y-%m-%d') if item.next_maintenance else '',
            item.notes
        ])

    output.seek(0)
    return send_file(
        StringIO(output.getvalue()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='inventory.csv'
    )

@app.route('/add', methods=['POST'])
def add_item():
    name = request.form['name']
    category = request.form['category']
    status = request.form['status']
    serial_number = request.form['serial_number']
    purchase_date = datetime.strptime(request.form['purchase_date'], '%Y-%m-%d') if request.form['purchase_date'] else None
    notes = request.form['notes']
    purchase_price = float(request.form['purchase_price']) if request.form['purchase_price'] else 0.0
    annual_depreciation_rate = float(request.form['annual_depreciation_rate']) if request.form['annual_depreciation_rate'] else 0.2

@app.route('/add_bulk', methods=['POST'])
def add_bulk_items():
    name = request.form['name']
    category = request.form['category']
    status = request.form['status']
    quantity = int(request.form['quantity'])
    purchase_date = datetime.strptime(request.form['purchase_date'], '%Y-%m-%d') if request.form['purchase_date'] else None
    purchase_price = float(request.form['purchase_price']) if request.form['purchase_price'] else 0.0
    annual_depreciation_rate = float(request.form['annual_depreciation_rate']) if request.form['annual_depreciation_rate'] else 0.2
    notes = request.form['notes']

    for i in range(quantity):
        new_item = Item(
            name=f"{name} #{i+1}",
            category=category,
            status=status,
            serial_number=f"BULK-{datetime.now().strftime('%Y%m%d')}-{i+1}",
            purchase_date=purchase_date,
            purchase_price=purchase_price,
            annual_depreciation_rate=annual_depreciation_rate,
            notes=notes
        )
        db.session.add(new_item)

    db.session.commit()
    return redirect(url_for('home'))

    new_item = Item(
        name=name,
        category=category,
        status=status,
        serial_number=serial_number,
        purchase_date=purchase_date,
        purchase_price=purchase_price,
        annual_depreciation_rate=annual_depreciation_rate,
        notes=notes
    )

    db.session.add(new_item)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/edit/<int:id>', methods=['POST'])
def edit_item(id):
    item = Item.query.get_or_404(id)
    item.name = request.form['name']
    item.category = request.form['category']
    item.status = request.form['status']
    item.serial_number = request.form['serial_number']
    item.purchase_date = datetime.strptime(request.form['purchase_date'], '%Y-%m-%d') if request.form['purchase_date'] else None
    item.next_maintenance = datetime.strptime(request.form['next_maintenance'], '%Y-%m-%d') if request.form['next_maintenance'] else None
    item.notes = request.form['notes']
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/maintenance/<int:id>', methods=['POST'])
def add_maintenance(id):
    item = Item.query.get_or_404(id)
    log = MaintenanceLog(
        item_id=id,
        description=request.form['description'],
        performed_by=request.form['performed_by']
    )
    db.session.add(log)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/delete/<int:id>')
def delete_item(id):
    item = Item.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/suggestions')
def get_suggestions():
    query = request.args.get('q', '')
    field = request.args.get('field', 'name')
    
    if field == 'name':
        items = Item.query.filter(Item.name.contains(query)).limit(5).all()
        suggestions = [item.name for item in items]
    elif field == 'category':
        items = Item.query.filter(Item.category.contains(query)).distinct(Item.category).limit(5).all()
        suggestions = [item.category for item in items]
    elif field == 'status':
        items = Item.query.filter(Item.status.contains(query)).distinct(Item.status).limit(5).all()
        suggestions = [item.status for item in items]
        
    return jsonify(suggestions)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
