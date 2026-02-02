"""
Script to set up test subscription data
"""
import database as db
from datetime import datetime, timedelta

conn = db.get_connection()
cur = conn.cursor()

# Insert subscription plans
print("Inserting subscription plans...")

cur.execute("""
    INSERT INTO SubscriptionPlan (name, display_name, price_cents, interval, stripe_price_id, features, is_active)
    VALUES ('free', 'Free', 0, 'month', NULL, '{"posts_per_month": 3, "delay_days": 3}', true)
    ON CONFLICT (name) DO NOTHING
""")

cur.execute("""
    INSERT INTO SubscriptionPlan (name, display_name, price_cents, interval, stripe_price_id, features, is_active)
    VALUES ('premium_monthly', 'Premium Monthly', 499, 'month', 'price_1SveGRQtG8HOa74dNIgGS7pB', '{"unlimited": true, "priority_support": true}', true)
    ON CONFLICT (name) DO UPDATE SET 
        stripe_price_id = EXCLUDED.stripe_price_id
""")

cur.execute("""
    INSERT INTO SubscriptionPlan (name, display_name, price_cents, interval, stripe_price_id, features, is_active)
    VALUES ('premium_annual', 'Premium Annual', 3900, 'year', 'price_1SveI1QtG8HOa74dzQhf2vU2', '{"unlimited": true, "priority_support": true}', true)
    ON CONFLICT (name) DO UPDATE SET 
        stripe_price_id = EXCLUDED.stripe_price_id
""")

conn.commit()

# Get premium plan ID
cur.execute("SELECT plan_id FROM SubscriptionPlan WHERE name = 'premium_monthly'")
premium_plan = cur.fetchone()
print(f"Premium plan ID: {premium_plan[0]}")

# Update user's stripe customer ID
user_id = 9
stripe_customer_id = 'cus_TtWEDvS09q9283'
stripe_subscription_id = 'sub_1SvjCrQtG8HOa74dexFSQ5tW'

print(f"Updating user {user_id} with Stripe customer ID...")

# First check if stripe_customer_id column exists on Users table
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'users' AND column_name = 'stripe_customer_id'
""")
if not cur.fetchone():
    print("Adding stripe_customer_id column to Users table...")
    cur.execute("ALTER TABLE Users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(100)")
    conn.commit()

cur.execute("""
    UPDATE Users SET stripe_customer_id = %s WHERE user_id = %s
""", (stripe_customer_id, user_id))

# Insert user subscription
print("Creating user subscription...")
current_period_start = datetime.now()
current_period_end = current_period_start + timedelta(days=30)

cur.execute("""
    INSERT INTO UserSubscription (user_id, plan_id, stripe_customer_id, stripe_subscription_id, status, current_period_start, current_period_end)
    VALUES (%s, %s, %s, %s, 'active', %s, %s)
    ON CONFLICT (user_id) DO UPDATE SET
        plan_id = EXCLUDED.plan_id,
        stripe_subscription_id = EXCLUDED.stripe_subscription_id,
        status = 'active',
        current_period_start = EXCLUDED.current_period_start,
        current_period_end = EXCLUDED.current_period_end
""", (user_id, premium_plan[0], stripe_customer_id, stripe_subscription_id, current_period_start, current_period_end))

conn.commit()

# Verify
cur.execute("""
    SELECT us.*, sp.display_name 
    FROM UserSubscription us 
    JOIN SubscriptionPlan sp ON us.plan_id = sp.plan_id 
    WHERE us.user_id = %s
""", (user_id,))
sub = cur.fetchone()
print(f"\n✅ Subscription created successfully!")
print(f"   User ID: {user_id}")
print(f"   Plan: {sub[-1]}")
print(f"   Status: {sub[5]}")
print(f"   Period End: {sub[7]}")

cur.close()
conn.close()
