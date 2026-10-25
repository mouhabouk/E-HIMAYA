"""Institutions an "organizations" message reaches (phase P2b), shared by notifications and the institution space.

``o`` is an ``org.organization`` row and ``m`` a ``notify.message`` row: active institutions in the message's
gouvernorats (all when empty) and of its kinds (all when empty).
"""

ORG_TARGET = """
    m.audience = 'organizations' AND o.status = 'active'
    AND (cardinality(m.gouvernorat_codes) = 0 OR o.gouvernorat_code = ANY(m.gouvernorat_codes))
    AND (cardinality(m.org_kinds) = 0 OR o.kind = ANY(m.org_kinds))
"""
