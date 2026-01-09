FROM python:3.12

ADD connectors/ .
ADD data_models/ .
ADD input_tables/ .
ADD sql_mappings/ .
ADD utils/ .
ADD __init__.py

RUN