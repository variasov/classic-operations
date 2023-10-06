# Classic Operations

This package provides primitives for application operations.
Part of project "Classic".

Usage:
```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, scoped_session, Session

from classic.operations import operation, Operation
from classic.components import component


class SomeRepo:
    def __init__(self, session: Session):
        self.session = session

    def select(self):
        self.session.execute(select(1))


@component
class Service:
    some_operation: Operation
    # new_operation prop name by default
    new_operation: Operation
    some_repo: SomeRepo
    
    # 95% case
    @operation
    def method_1(self):
        self.some_repo.select()

    @operation(prop_name='some_operation')
    def method_2(self):
        self.some_repo.select()

    def method_3(self):
        with self.some_operation as op:
            if None:
                self.some_repo.select()
                op.complete()
    
    def method_4(self):
        with self.some_operation:
            self.some_repo.select()
    
    def method_5(self):
        with self.some_operation as op:
            op.on_complete(lambda: print('Hello'))


class DB:
    engine = create_engine('DB_URL')
    session = scoped_session(sessionmaker(bind=engine))

    
transaction_operation = Operation(
    on_complete=[DB.session.commit],
    on_cancel=[DB.session.rollback],
)

repo = SomeRepo(session=DB.session)
service = Service(
    new_operation=transaction_operation,
    some_operation=transaction_operation,
    some_repo=repo,
)

service.method()
```
