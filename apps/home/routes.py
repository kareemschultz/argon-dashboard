# -*- encoding: utf-8 -*-
from flask import render_template, request, jsonify
from apps.home import blueprint
from jinja2 import TemplateNotFound
from decimal import Decimal, ROUND_HALF_UP
import requests
import json
import dns.resolver
import speedtest
import qrcode
import hashlib
from io import BytesIO
import base64

# Dashboard route
@blueprint.route('/')
def index():
    return render_template('home/index.html', segment='index')

# Salary Calculator routes
# Add to your routes.py file

@blueprint.route('/salary-calculator')
def salary_calculator():
    return render_template('home/salary-calculator.html', segment='salary-calculator')

@blueprint.route('/calculate-salary', methods=['POST'])
def calculate_salary():
    try:
        # Get basic salary
        basic_salary = float(request.form.get('basic_salary', 0))
        
        # Process taxable allowances
        num_taxable = int(request.form.get('num_taxable', 0))
        taxable_allowances = []
        for i in range(num_taxable):
            allowance = float(request.form.get(f'taxable_allowance_{i}', 0))
            taxable_allowances.append(allowance)
        
        # Process non-taxable allowances
        num_non_taxable = int(request.form.get('num_non_taxable', 0))
        non_taxable_allowances = []
        for i in range(num_non_taxable):
            allowance = float(request.form.get(f'non_taxable_allowance_{i}', 0))
            non_taxable_allowances.append(allowance)
        
        # Get insurance details
        insurance_type = request.form.get('insurance_type')
        if insurance_type == '5':  # 3rd Party Provider
            insurance_premium = float(request.form.get('insurance_premium', 0))
        else:
            # Predefined Assuria amounts
            insurance_amounts = {
                '1': 0,          # No Coverage
                '2': 1469,       # Employee Only
                '3': 3182,       # Employee & One
                '4': 4970       # Employee & Family
            }
            insurance_premium = insurance_amounts.get(insurance_type, 0)

        # Get other deductions
        loan_deduction = float(request.form.get('loan_deduction', 0))
        gpsu_deduction = float(request.form.get('gpsu_deduction', 0))
        num_children = int(request.form.get('num_children', 0))

        # Calculate totals
        total_taxable_allowances = sum(taxable_allowances)
        total_non_taxable_allowances = sum(non_taxable_allowances)
        
        # Calculate gross pay
        gross_pay = basic_salary + total_taxable_allowances + total_non_taxable_allowances
        
        # Calculate personal allowance with children
        personal_allowance = 100000 + (num_children * 10000)
        
        # Calculate NIS (5.6% with cap of $15,680)
        nis_rate = 0.056
        nis_cap = 15680
        nis_contribution = min(basic_salary * nis_rate, nis_cap)
        
        # Calculate insurance deduction (max 10% of gross or $50,000)
        max_insurance = min(insurance_premium, gross_pay * 0.1, 50000)
        
        # Calculate chargeable income
        if basic_salary < personal_allowance:
            chargeable_income = 0
            paye_tax = 0
        else:
            chargeable_income = (basic_salary - personal_allowance - nis_contribution - max_insurance)
            
            # Calculate PAYE tax
            if chargeable_income <= 2400000:
                paye_tax = chargeable_income * 0.28
            else:
                paye_tax = (2400000 * 0.28) + ((chargeable_income - 2400000) * 0.4)
        
        # Calculate total deductions and net pay
        total_deductions = nis_contribution + paye_tax + loan_deduction + gpsu_deduction + max_insurance
        net_pay = gross_pay - total_deductions
        
        # Calculate gratuity
        monthly_gratuity = basic_salary * 0.225
        semi_annual_gratuity = monthly_gratuity * 6
        annual_gratuity = monthly_gratuity * 12

        return jsonify({
            'success': True,
            'data': {
                'gross_pay': round(gross_pay, 2),
                'net_pay': round(net_pay, 2),
                'total_deductions': round(total_deductions, 2),
                'monthly_gratuity': round(monthly_gratuity, 2),
                'semi_annual_gratuity': round(semi_annual_gratuity, 2),
                'annual_gratuity': round(annual_gratuity, 2),
                'personal_allowance': round(personal_allowance, 2),
                'nis_contribution': round(nis_contribution, 2),
                'insurance_deduction': round(max_insurance, 2),
                'chargeable_income': round(chargeable_income, 2),
                'paye_tax': round(paye_tax, 2)
            }
        })

    except Exception as e:
        print(f"Error in calculate_salary: {str(e)}")  # For debugging
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
        
        
# apps/home/routes.py

@blueprint.route('/vehicle-import')
def vehicle_import():
    return render_template('home/vehicle-import.html', segment='vehicle-import')

@blueprint.route('/calculate-import', methods=['POST'])
def calculate_import():
    try:
        # Get form data
        cif_usd = float(request.form.get('cif'))
        exchange_rate = float(request.form.get('exchange_rate', 208.50))
        vehicle_age = request.form.get('vehicle_age')
        vehicle_type = request.form.get('vehicle_type')
        propulsion = request.form.get('propulsion')
        engine_cc = request.form.get('engine_cc')
        plate_type = request.form.get('plate_type', 'P')

        # Convert CIF to GYD
        cif_gyd = cif_usd * exchange_rate

        # Electric vehicles have zero taxes
        if propulsion == 'electric':
            return jsonify({
                'success': True,
                'calculations': {
                    'cif_gyd': round(cif_gyd, 2),
                    'excise_tax': 0,
                    'vat': 0,
                    'custom_duty': 0,
                    'total_cost': round(cif_gyd, 2)
                }
            })

        # Calculate based on vehicle age
        if vehicle_age == 'old':  # 4 years and older
            # Calculate excise tax based on engine size for vehicles 4 years and older
            excise_tax = calculate_old_vehicle_excise(cif_gyd, engine_cc, propulsion)
            custom_duty = 0  # No duty for vehicles 4 years and older
            vat = 0  # No VAT for vehicles 4 years and older
            
        else:  # Under 4 years
            # Calculate taxes for vehicles under 4 years
            duty_rate, excise_rate, vat_rate = get_new_vehicle_rates(engine_cc, propulsion)
            
            custom_duty = cif_gyd * duty_rate
            excise_tax = (cif_gyd + custom_duty) * excise_rate
            vat = (cif_gyd + custom_duty + excise_tax) * vat_rate

        # Calculate total cost
        total_cost = cif_gyd + excise_tax + vat + custom_duty

        return jsonify({
            'success': True,
            'calculations': {
                'cif_gyd': round(cif_gyd, 2),
                'excise_tax': round(excise_tax, 2),
                'vat': round(vat, 2),
                'custom_duty': round(custom_duty, 2),
                'total_cost': round(total_cost, 2)
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

def calculate_old_vehicle_excise(cif_gyd, engine_cc, propulsion):
    """Calculate excise tax for vehicles 4 years and older"""
    if propulsion == 'gasoline':
        if engine_cc in ['0-1000', '1001-1500']:
            return 800000  # Flat rate
        elif engine_cc == '1501-1800':
            return (cif_gyd + (6000 * 208.50)) * 0.3 + (6000 * 208.50)
        elif engine_cc == '1801-2000':
            return (cif_gyd + (6500 * 208.50)) * 0.3 + (6500 * 208.50)
        elif engine_cc == '2001-3000':
            return (cif_gyd + (13500 * 208.50)) * 0.7 + (13500 * 208.50)
        else:  # Over 3000cc
            return (cif_gyd + (14500 * 208.50)) * 1.0 + (14500 * 208.50)
    else:  # Diesel
        if engine_cc in ['0-1000', '1001-1500']:
            return 800000  # Flat rate
        elif engine_cc in ['1501-1800', '1801-2000']:
            return (cif_gyd + (15400 * 208.50)) * 0.3 + (15400 * 208.50)
        elif engine_cc == '2001-3000':
            return (cif_gyd + (15400 * 208.50)) * 0.7 + (15400 * 208.50)
        else:  # Over 3000cc
            return (cif_gyd + (17200 * 208.50)) * 1.0 + (17200 * 208.50)

def get_new_vehicle_rates(engine_cc, propulsion):
    """Get duty, excise, and VAT rates for vehicles under 4 years"""
    if propulsion == 'gasoline':
        if engine_cc in ['0-1000', '1001-1500']:
            return 0.35, 0, 0.14  # duty, excise, VAT
        elif engine_cc in ['1501-1800', '1801-2000']:
            return 0.45, 0.10, 0.14
        elif engine_cc == '2001-3000':
            return 0.45, 1.10, 0.14
        else:  # Over 3000cc
            return 0.45, 1.40, 0.14
    else:  # Diesel
        if engine_cc in ['0-1000', '1001-1500']:
            return 0.35, 0, 0.14
        elif engine_cc == '1501-1800':
            return 0.45, 0.10, 0.14
        else:  # 2000cc and above
            return 0.45, 1.10, 0.14
        
# Public IP routes
@blueprint.route('/public-ip')
def public_ip():
    return render_template('home/public-ip.html', segment='public-ip')

@blueprint.route('/get-ip-info', methods=['GET'])
def get_ip_info():
    try:
        # Using ipapi.co for detailed IP information
        response = requests.get('https://ipapi.co/json/')
        if response.status_code == 200:
            data = response.json()
            # Add additional hostname lookup
            try:
                hostname = socket.gethostbyaddr(data['ip'])[0]
            except:
                hostname = None
            
            data['hostname'] = hostname
            return jsonify(data)
        else:
            return jsonify({'error': 'Failed to fetch IP information'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@blueprint.route('/dns-lookup')
def dns_lookup():
    return render_template('home/dns-lookup.html', segment='dns-lookup')

@blueprint.route('/lookup-dns', methods=['POST'])
def lookup_dns():
    try:
        domain = request.form.get('domain')
        if not domain:
            return jsonify({
                'success': False,
                'error': 'Domain name is required'
            }), 400

        record_types = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'SOA', 'CNAME', 'PTR']
        results = {}

        for record_type in record_types:
            try:
                answers = dns.resolver.resolve(domain, record_type)
                results[record_type] = {
                    'records': [str(rdata) for rdata in answers],
                    'ttl': answers.rrset.ttl
                }
            except Exception as e:
                results[record_type] = {
                    'records': [],
                    'error': str(e)
                }

        # Add WHOIS information if possible
        try:
            import whois
            whois_info = whois.whois(domain)
            results['WHOIS'] = whois_info
        except:
            results['WHOIS'] = None

        return jsonify({
            'success': True,
            'domain': domain,
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# Speed Test routes
@blueprint.route('/speedtest')
def speedtest_page():
    return render_template('home/speedtest.html', segment='speedtest')

@blueprint.route('/run-speedtest', methods=['POST'])
def run_speedtest():
    try:
        st = speedtest.Speedtest()
        
        # Get server list and select best
        st.get_best_server()
        
        # Track progress
        progress = {
            'download': 0,
            'upload': 0,
            'ping': 0
        }
        
        # Download Speed
        download_speed = st.download() / 1_000_000  # Convert to Mbps
        progress['download'] = 100
        
        # Upload Speed
        upload_speed = st.upload() / 1_000_000  # Convert to Mbps
        progress['upload'] = 100
        
        # Ping
        ping = st.results.ping
        progress['ping'] = 100
        
        # Get server information
        server_info = st.get_best_server()
        
        return jsonify({
            'success': True,
            'results': {
                'download': round(download_speed, 2),
                'upload': round(upload_speed, 2),
                'ping': round(ping, 2),
                'server': {
                    'name': server_info['sponsor'],
                    'location': f"{server_info['city']}, {server_info['country']}",
                    'host': server_info['host']
                }
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
        
# About & Contact Routes
@blueprint.route('/about')
def about():
    return render_template('home/about.html', segment='about')

@blueprint.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            email = request.form.get('email')
            subject = request.form.get('subject')
            message = request.form.get('message')
            
            # Here you would typically send an email or store in database
            # For now, we'll just return success
            return jsonify({
                'success': True,
                'message': 'Message sent successfully!'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
            
    return render_template('home/contact.html', segment='contact')

# Currency Converter Routes
@blueprint.route('/currency-converter')
def currency_converter():
    return render_template('home/currency-converter.html', segment='currency-converter')

@blueprint.route('/convert-currency', methods=['POST'])
def convert_currency():
    try:
        amount = float(request.form.get('amount'))
        from_currency = request.form.get('from_currency')
        to_currency = request.form.get('to_currency')
        
        # You would typically use a currency API here
        # For example, using exchangerate-api.com
        API_KEY = os.getenv('EXCHANGE_RATE_API_KEY')
        
        # Make API request
        response = requests.get(
            f'https://v6.exchangerate-api.com/v6/{API_KEY}/pair/{from_currency}/{to_currency}/{amount}'
        )
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                'success': True,
                'result': {
                    'amount': amount,
                    'from_currency': from_currency,
                    'to_currency': to_currency,
                    'converted_amount': data['conversion_result'],
                    'rate': data['conversion_rate'],
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            })
        else:
            raise Exception('Failed to fetch exchange rate')
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@blueprint.route('/get-exchange-rates', methods=['GET'])
def get_exchange_rates():
    try:
        base_currency = request.args.get('base', 'USD')
        
        # Fetch latest rates
        API_KEY = os.getenv('EXCHANGE_RATE_API_KEY')
        response = requests.get(
            f'https://v6.exchangerate-api.com/v6/{API_KEY}/latest/{base_currency}'
        )
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'rates': response.json()['conversion_rates']
            })
        else:
            raise Exception('Failed to fetch rates')
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# Error handlers
@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404

@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 50