#!/bin/bash
# Check user access to LDAP

# apt install ldap-utils
# brew install openldap

HOST="10.0.0.1"
BASE="dc=ad,dc=local"

USER="username"
USER_DN="cn=${USER},ou=some_ou,dc=ad,dc=local"
PASS="pass for ${USER}"

LDAPTLS_REQCERT=allow \
    ldapsearch -LLL -H "ldaps://$HOST" \
    -b "$BASE" \
    -D "$USER_DN" \
    -w "$PASS" \
    sAMAccountName="$USER" memberOf
