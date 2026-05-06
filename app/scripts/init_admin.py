import asyncio
import sys
from datetime import datetime, timezone

from app.core.database import connect_to_mongo, close_mongo_connection
from app.models.user import User, UserStatus, UserRole
from app.core.security import hash_password
from app.utils.logger import app_logger


async def create_admin_user(
    email: str = "user@example.com",
    password: str = "string",
    full_name: str = "System Administrator",
):
    """Create initial admin user"""
    try:
        await connect_to_mongo()

        # Check if admin already exists
        existing_admin = await User.find_one(User.email == email)
        if existing_admin:
            print(f"Admin user with email {email} already exists!")
            return existing_admin

        # Create admin user
        admin_user = User(
            user_id="ADM001",
            email=email,
            phone="9999999999",
            fname="System",
            lname="Administrator",
            full_name=full_name,
            password=hash_password(password),
            user_type=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            email_verified=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        await admin_user.insert()

        print("Admin user created successfully!")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"Role: {admin_user.user_type}")
        print(f"Status: {admin_user.status}")
        print(f"ID: {admin_user.id}")

        app_logger.info(f"Admin user created: {email}")
        return admin_user

    except Exception as e:
        print(f"Error creating admin user: {str(e)}")
        app_logger.error(f"Failed to create admin user: {str(e)}")
        raise

    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m app.scripts.init_admin create [email] [password] [full_name]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "create":
        email = sys.argv[2] if len(sys.argv) > 2 else "user@example.com"
        password = sys.argv[3] if len(sys.argv) > 3 else "string"
        full_name = sys.argv[4] if len(sys.argv) > 4 else "System Administrator"

        asyncio.run(create_admin_user(email, password, full_name))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
