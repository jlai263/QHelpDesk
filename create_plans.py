from app import create_app, db
from app.models import SubscriptionPlan

app = create_app()
with app.app_context():
    # Define the subscription plans
    plans = [
        {
            'name': 'Free',
            'price': 0.0,
            'team_size_limit': 5,
            'description': 'Perfect for small teams just getting started',
            'features': [
                'Up to 5 team members',
                'Basic ticket management',
                'Email support'
            ]
        },
        {
            'name': 'Professional',
            'price': 15.0,
            'team_size_limit': 25,
            'description': 'Ideal for growing teams with advanced needs',
            'features': [
                'Up to 25 team members',
                'Advanced ticket management',
                'AI-powered responses',
                'Priority support'
            ]
        },
        {
            'name': 'Enterprise',
            'price': 50.0,
            'team_size_limit': 999999999,  # Effectively unlimited
            'description': 'Full-featured solution for large organizations',
            'features': [
                'Unlimited team members',
                'Advanced analytics',
                'All Professional features',
                'Custom integrations'
            ]
        }
    ]

    # Add plans to database if they don't exist
    for plan_data in plans:
        if not SubscriptionPlan.query.filter_by(name=plan_data['name']).first():
            plan = SubscriptionPlan(
                name=plan_data['name'],
                price=plan_data['price'],
                team_size_limit=plan_data['team_size_limit'],
                description=plan_data['description'],
                features=plan_data['features'],
                is_active=True
            )
            db.session.add(plan)
            print(f"Added {plan_data['name']} plan")
    
    # Commit the changes
    db.session.commit()
    print("All subscription plans created successfully!") 