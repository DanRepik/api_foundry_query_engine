"""Operation.roles from the claims each kind of authorizer passes."""

import pytest

from api_foundry_query_engine.operation import Operation


def roles(claims):
    return Operation(entity="album", action="read", claims=claims).roles


@pytest.mark.unit
class TestOperationRoles:
    def test_roles_claim_wins(self):
        assert roles({"roles": ["admin"], "cognito:groups": "member"}) == ["admin"]
        assert roles({"roles": "admin"}) == ["admin"]

    def test_role_and_groups(self):
        assert roles({"role": "admin", "groups": ["admin", "member"]}) == ["admin", "member"]
        assert roles({"groups": '["sales", "support"]'}) == ["sales", "support"]
        assert roles({"groups": "sales"}) == ["sales"]

    @pytest.mark.parametrize(
        "value,expected",
        [
            (["admin", "member"], ["admin", "member"]),     # a JWT decoded in-process
            ('["admin","member"]', ["admin", "member"]),    # JSON text
            ("[admin member]", ["admin", "member"]),        # API Gateway's rendering of a list claim
            ("[admin, member]", ["admin", "member"]),
            ("admin,member", ["admin", "member"]),
            ("member", ["member"]),
            ("", []),
            (None, []),
        ],
    )
    def test_cognito_groups(self, value, expected):
        """A Cognito user pool authorizer passes the user's groups as
        cognito:groups, not roles or groups."""
        assert roles({"sub": "u-1", "cognito:groups": value}) == expected

    def test_groups_and_cognito_groups_merge_without_repeats(self):
        assert roles({"groups": ["member"], "cognito:groups": "[member admin]"}) == ["member", "admin"]

    def test_no_claims(self):
        assert roles({}) == []
        assert roles({"sub": "u-1"}) == []
