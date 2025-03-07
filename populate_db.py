from app import app, db, User, BrandReview, BrandLike
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

def populate_db():
    # Clear existing data
    db.drop_all()
    db.create_all()

    # Create default brands
    brands = [
        {
            'username': 'adidas',
            'email': 'adidas@example.com',
            'password': 'password123',
            'brand_name': 'Adidas',
            'logo_filename': 'adidas-trefoil-logo-design.webp'
        },
        {
            'username': 'puma',
            'email': 'puma@example.com',
            'password': 'password123',
            'brand_name': 'Puma',
            'logo_filename': '360_F_202177215_ImnfbtEengMzSOzGISGZKvjt9gGFiynq.webp'  # Updated Puma logo
        },
        {
            'username': 'crocs',
            'email': 'crocs@example.com',
            'password': 'password123',
            'brand_name': 'Crocs',
            'logo_filename': 'crocs.webp'
        },
        {
            'username': 'trends',
            'email': 'trends@example.com',
            'password': 'password123',
            'brand_name': 'Trends',
            'logo_filename': '280.webp'  # Trends logo
        },
        {
            'username': 'max',
            'email': 'max@example.com',
            'password': 'password123',
            'brand_name': 'Max',
            'logo_filename': '8d8UvSPK2Ue9qRzDG7JJ5F-1000-80.webp'  # Max logo
        },
        {
            'username': 'zara',
            'email': 'zara@example.com',
            'password': 'password123',
            'brand_name': 'Zara',
            'logo_filename': '388ad7154062515e9148ef2fbbb31ba9daeafc6c-1096x619.webp'  # Updated Zara logo
        },
        {
            'username': 'boat',
            'email': 'boat@example.com',
            'password': 'password123',
            'brand_name': 'Boat',
            'logo_filename': 'logaster-2020-08-t-boat-logo-6.webp'
        },
        {
            'username': 'apple',
            'email': 'apple@example.com',
            'password': 'password123',
            'brand_name': 'Apple',
            'logo_filename': 'Apple_logo_grey-624x400.webp'
        },
        {
            'username': 'lifestyle',
            'email': 'lifestyle@example.com',
            'password': 'password123',
            'brand_name': 'Lifestyle',
            'logo_filename': 'Lifestyle_Stores_-_New.webp'
        }
    ]

    # Add brands
    for brand_data in brands:
        brand = User(
            username=brand_data['username'],
            email=brand_data['email'],
            password_hash=generate_password_hash(brand_data['password']),
            is_brand=True,
            brand_name=brand_data['brand_name'],
            logo_filename=brand_data['logo_filename']
        )
        db.session.add(brand)

    # Create some regular users
    users = [
        {
            'username': 'user1',
            'email': 'user1@example.com',
            'password': 'password123'
        },
        {
            'username': 'user2',
            'email': 'user2@example.com',
            'password': 'password123'
        }
    ]

    for user_data in users:
        user = User(
            username=user_data['username'],
            email=user_data['email'],
            password_hash=generate_password_hash(user_data['password']),
            is_brand=False
        )
        db.session.add(user)

    # Commit the changes
    db.session.commit()

    # Add some sample reviews and likes
    brands = User.query.filter_by(is_brand=True).all()
    users = User.query.filter_by(is_brand=False).all()

    for brand in brands:
        # Add reviews
        for user in users:
            review = BrandReview(
                rating=random.randint(3, 5),
                comment=f"Great brand with excellent products! Would recommend {brand.brand_name} to everyone.",
                user_id=user.id,
                brand_id=brand.id
            )
            db.session.add(review)

            # Add likes
            like = BrandLike(
                user_id=user.id,
                brand_id=brand.id
            )
            db.session.add(like)

        # Add some shares
        brand.shares = random.randint(5, 20)

    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        populate_db()
        print("Database populated successfully!") 