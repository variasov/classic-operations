from classic.operations import NewOperation, operation
from classic.persistence.core import GenericRepository


class Service:
    new_operation: NewOperation

    def method_1(self):
        op = self.new_operation()
        try:
            pass
        except Exception:
            op.rollback()
            raise
        else:
            op.commit()
        finally:
            op.close()

    def method_2(self):
        with self.new_operation() as op:
            if None:
                op.commit()

    # 95% case
    @operation
    def method_3(self):
        pass

    def method_4(self):
        with self.new_operation() as op:
            op.on_commit(lambda: print('Hello'))


class Loader:
    new_read_operation: NewOperation
    new_write_operation: NewOperation

    source: GenericRepository
    target: GenericRepository

    @operation(prop_name='new_read_operation')
    def load(self):
        for entity in self.source.all():
            op = self.new_write_operation()
            self.target.save(entity)
            op.commit()
