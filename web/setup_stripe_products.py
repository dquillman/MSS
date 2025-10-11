"""
Setup Stripe products and prices for MSS
Run this after adding your Stripe API keys to .env
"""
import os
import stripe
from pathlib import Path

# Load .env
def load_env():
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

load_env()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

if not stripe.api_key or stripe.api_key == 'sk_test_YOUR_SECRET_KEY_HERE':
    print("❌ Error: STRIPE_SECRET_KEY not set in .env file")
    print("Please add your Stripe secret key to G:\\Users\\daveq\\mss\\.env")
    exit(1)

print("🔧 Setting up Stripe products and prices...\n")

# Product definitions
products = [
    {
        'name': 'MSS Starter Plan',
        'description': '30 videos per month with all features unlocked',
        'price': 1900,  # $19.00 in cents
        'interval': 'month',
        'price_key': 'STRIPE_PRICE_STARTER'
    },
    {
        'name': 'MSS Pro Plan',
        'description': 'Unlimited videos with priority support',
        'price': 4900,  # $49.00 in cents
        'interval': 'month',
        'price_key': 'STRIPE_PRICE_PRO'
    },
    {
        'name': 'MSS Agency Plan',
        'description': 'Unlimited everything with white label and API access',
        'price': 14900,  # $149.00 in cents
        'interval': 'month',
        'price_key': 'STRIPE_PRICE_AGENCY'
    },
    {
        'name': 'MSS Lifetime Access',
        'description': 'Unlimited videos forever - one-time payment',
        'price': 19900,  # $199.00 in cents
        'interval': None,  # One-time payment
        'price_key': 'STRIPE_PRICE_LIFETIME'
    }
]

price_ids = {}

for product_def in products:
    try:
        # Check if product already exists
        existing_products = stripe.Product.list(limit=100)
        existing = None
        for p in existing_products.data:
            if p.name == product_def['name']:
                existing = p
                break

        if existing:
            print(f"✓ Product exists: {product_def['name']}")
            product = existing
        else:
            # Create product
            product = stripe.Product.create(
                name=product_def['name'],
                description=product_def['description']
            )
            print(f"✓ Created product: {product_def['name']}")

        # Check if price already exists for this product
        existing_prices = stripe.Price.list(product=product.id, limit=10)
        price = None

        for ep in existing_prices.data:
            if product_def['interval']:
                # Recurring price
                if (ep.unit_amount == product_def['price'] and
                    ep.recurring and
                    ep.recurring.interval == product_def['interval']):
                    price = ep
                    break
            else:
                # One-time price
                if ep.unit_amount == product_def['price'] and not ep.recurring:
                    price = ep
                    break

        if price:
            print(f"  ✓ Price exists: ${product_def['price']/100:.2f}")
        else:
            # Create price
            price_params = {
                'product': product.id,
                'unit_amount': product_def['price'],
                'currency': 'usd',
            }

            if product_def['interval']:
                price_params['recurring'] = {'interval': product_def['interval']}

            price = stripe.Price.create(**price_params)
            print(f"  ✓ Created price: ${product_def['price']/100:.2f}")

        price_ids[product_def['price_key']] = price.id

    except Exception as e:
        print(f"❌ Error creating {product_def['name']}: {e}")
        continue

# Print env variables to add
print("\n" + "="*60)
print("✅ Setup complete! Add these to your .env file:")
print("="*60 + "\n")

for key, price_id in price_ids.items():
    print(f"{key}={price_id}")

print("\n" + "="*60)
print("Next steps:")
print("1. Copy the lines above to your .env file")
print("2. Restart your API server")
print("3. Test payments at http://localhost:5000/pricing")
print("="*60)
