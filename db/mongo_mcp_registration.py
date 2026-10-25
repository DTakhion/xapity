# db/mongo_mcp_registration.py
from __future__ import annotations

from datetime import datetime, timezone
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from db.mongo_persistence import get_database
from db.mongo_mcp_auth_persistence import MCP_PROVISIONING_PURPOSE


def initialize_mcp_registration_storage():
    db = get_database()
    db.mcp_users.create_index('email', unique=True, name='ux_mcp_user_email')
    db.mcp_users.create_index('userId', unique=True, name='ux_mcp_user_id')
    db.mcp_pending_registrations.create_index('email', unique=True, name='ux_mcp_pending_email')
    db.mcp_pending_registrations.create_index('expiresAt', expireAfterSeconds=0, name='ttl_mcp_pending_expiry')


def get_mcp_user_by_email(email: str):
    return get_database().mcp_users.find_one({'email': email})


def get_mcp_user_by_id(user_id: str):
    return get_database().mcp_users.find_one({
        'userId': user_id,
        'accountType': 'mcp',
        'isActive': True,
        'isDeleted': False,
    })



def save_mcp_pending_registration(document: dict):
    db = get_database()
    db.mcp_pending_registrations.update_one(
        {'email': document['email']}, {'$set': document}, upsert=True
    )


def get_mcp_pending_registration(email: str):
    return get_database().mcp_pending_registrations.find_one({'email': email})


def increment_mcp_pending_attempts(email: str, expected_attempts: int):
    return get_database().mcp_pending_registrations.update_one(
        {'email': email, 'attempts': expected_attempts, 'usedAt': None},
        {'$inc': {'attempts': 1}}
    ).modified_count == 1


def finalize_mcp_registration(email: str, code_hash: str, user: dict):
    """Commit user creation, invitation consumption, and pending deletion atomically."""
    db = get_database()
    now = datetime.now(timezone.utc)
    with db.client.start_session() as session:
        with session.start_transaction():
            pending = db.mcp_pending_registrations.find_one(
                {'email': email, 'codeHash': code_hash, 'usedAt': None,
                 'expiresAt': {'$gt': now}, 'attempts': {'$lt': 5}},
                session=session,
            )
            if not pending:
                raise ValueError('Registro MCP inválido o expirado')

            invitation = db.mcp_user_provisioning_tokens.find_one_and_update(
                {'tokenHash': pending['provisioningTokenHash'], 'email': email,
                 'purpose': MCP_PROVISIONING_PURPOSE, 'usedAt': None,
                 'expiresAt': {'$gt': now}, 'scopes': ['luca:sales:read']},
                {'$set': {'usedAt': now, 'updatedAt': now}},
                session=session,
            )
            if not invitation:
                raise ValueError('Invitación MCP inválida o expirada')

            db.mcp_users.insert_one(user, session=session)
            db.mcp_pending_registrations.delete_one({'_id': pending['_id']}, session=session)
    return user
