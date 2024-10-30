# devtools.sh

# api operations
alias up="pulumilocal up --yes --stack local"
alias down="pulumilocal destroy --yes --stack local"

alias postgres_secret="install_secret --secret-name \"postgres/chinook\" \
  --engine postgres \
  --host postgres_db \
  --database chinook_auto_increment \
  --user chinook_user \
  --password chinook_password \
  --schema public"

# playground operations
alias infra_up="playground postgres; postgres_secret"
alias infra_down="playground down"
alias infra_reset="playground reset"
