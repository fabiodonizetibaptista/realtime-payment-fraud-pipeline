-- Etapa 8: definição de chave primária para accounts.
-- Executar somente se account_id ainda não for PRIMARY KEY.
-- Requer permissões de alteração estrutural na Confluent.
-- A instrução abaixo não é automaticamente executada pelo Terraform.

ALTER TABLE `desafio-final`.`desafio-basic`.`payments.public.accounts`
ADD CONSTRAINT pk_accounts
PRIMARY KEY (account_id) NOT ENFORCED;

-- Validação após a alteração:
DESCRIBE `desafio-final`.`desafio-basic`.`payments.public.accounts`;
