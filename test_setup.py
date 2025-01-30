from app import create_app, db
from app.models import User, Organization, Invitation
from datetime import datetime, timedelta
import uuid

app = create_app()

def setup_test_data():
    with app.app_context():
        # Create test organization
        org = Organization(
            name='Test Company',
            domain='test.com'
        )
        db.session.add(org)
        db.session.commit()
        
        # Create admin user
        admin = User(
            username='admin',
            email='admin@test.com',
            role='admin',
            organization_id=org.id
        )
        admin.set_password('password123')
        db.session.add(admin)
        db.session.commit()
        
        # Create test invitation
        invitation = Invitation(
            email='test@test.com',
            organization_id=org.id,
            token=str(uuid.uuid4()),
            expires_at=datetime.utcnow() + timedelta(days=7),
            is_admin_invite=False
        )
        db.session.add(invitation)
        db.session.commit()
        
        print("Test data created successfully!")
        print(f"Admin credentials: admin@test.com / password123")
        print(f"Invitation token for test@test.com: {invitation.token}")

if __name__ == '__main__':
    setup_test_data() 