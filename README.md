# Classic Operations

Библиотека предоставляет примитив для выделения границ операций в приложении.

## Введение

Общая проблема, которую эта библиотека решает, это выделение границ операций
у приложения и вызов на границах стороннего кода, не имеющего отношения
к приложению.

Самый частый пример - использование транзакций в приложении. С одной стороны,
хочется иметь декоратор вроде `transactional`, которым можно было бы просто
обернуть метод в приложении, с другой стороны, хотелось бы, чтобы приложение 
не упоминало транзакции, так как это все-так больше имеет отношение к БД.

Объект-операция представляет собой контейнер, в которой можно положить
контекстные менеджеры, и/или коллбеки. Затем объект операцию можно стартовать,
при старте отработают контекстные менеджеры и коллбеки, затем, при завершении,
соответствующие коллбеки и закроются контекстные менеджеры.

Пример:

```python
from classic.operations import Operation, operation
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


# Код приложения
class SomeService:
    
    # Dependency Injection
    def __init__(self, operation_: Operation):
        self.operation_ = operation_

    def some_method(self):
        with self.operation_:
            print('Здесь должна происходить полезная работа')
    
    @operation
    def another_method(self):
        """Этот метод полностью аналогичен some_method.
        Декоратор operation внутри обращается к self.operation_,
        и так же помещает в блок with. Сделано ради сахара.
        """
        print('Здесь должна происходить полезная работа')

# Композит
engine = create_engine('sqlite://')
session = Session(engine)
operation_ = Operation(context_managers=[session])
service = SomeService(operation_=operation_)

# Где-то в клиентском коде, например, в адаптерах:
service.some_method()
```

В примере каждый вызов some_method будет запуском операции. При входе в блок
with будет вызван `__enter__` у сессии, при выходе - `__exit__`, и, 
таким образом, произойдет обертывание метода в транзакцию, хотя код сервиса
напрямую ничего о транзакции не упоминает.

## Callbacks
Также можно повешать коллбеки на разные точки в жизненном цикле.
Коллбеки не должны принимать никаких аргументов.

В примере указаны все возможные коллбеки:

```python
from functools import partial
from classic.operations import Operation


lazy_print = partial(print)

operation_ = Operation(
    before_start=[lazy_print('Попытка начать операцию')],
    after_start=[lazy_print('Операция начата')],
    before_complete=[lazy_print('Операция успешно подходит к завершению')],
    after_complete=[lazy_print('Операция успешно завершена')],
    on_cancel=[lazy_print('Операция отменена')],
    on_finish=[lazy_print('Это вызовется после завершения '
                          'операции в любом случае')],
)
```

Порядок вызова при входе в блок `with` (`__enter__`):

- `before_start`. Если хотя бы один из них вызовет исключение, 
  исполнение прервется, будут вызваны `on_cancel` и `on_finish`, исключение
  будет выброшено наружу.

- `__enter__` у всех контекстных менеджеров, переданных в операцию. Если хотя бы 
  из них вызовет исключение, исполнение прервется, будут вызваны `on_cancel` и 
  `on_finish`, исключение будет выброшено наружу.

- `after_start`. Если хотя бы один из них вызовет исключение, 
  исполнение прервется, будут вызваны `on_cancel` и `on_finish`, исключение
  будет выброшено наружу.


Порядок вызова при выходе из блока `with` (`__exit__`):

- `before_complete`. Если хотя бы один из них вызовет исключение, исполнение 
  не прервется сразу, так как необходимо попытаться вызвать `__exit__` у всех 
  контекстных менеджеров из операции. Исключение будет отложено, но на 
  следующем шаге оно будет передано в `__exit__` каждому контекстному менеджеру.

- `__exit__` у всех контекстных менеджеров, переданных в операцию. Если хотя бы 
  один из них вызовет исключение, исполнение не должно прерваться, сразу, все
  методы `__exit__` у всех вложенных контекстных менеджеров должны быть вызваны. 

  Если при этом произошло исключение, или есть исключение, отложенное 
  с предыдущего шага, то исполнение прервется, будут вызваны `on_cancel` и 
  `on_finish`, исключение будет выброшено наружу.

- `after_complete`. Если хотя бы из них вызовет исключение, 
  исполнение прервется, будут вызваны `on_cancel` и `on_finish`, исключение будет
  выброшено наружу


## Динамические callbacks

Объект-операция предоставляет способ добавить коллбеки уже после запуска 
самой операции, внутри блока `with`. Такие коллбеки будут одноразовыми,
объект-операция забудет о них после завершения текущей операции. 

Вне запущенный операции эти методы вызывать нельзя, они будут генерировать
исключение `AssertionError`

Пример: 

```python
from classic.operations import Operation, operation

class SomeService:
    
    # Dependency Injection
    def __init__(self, operation_: Operation):
        self.operation_ = operation_

    @operation
    def some_method(self):
        self.operation_.after_complete(
            lambda: print('Операция завершена успешно')
        )
        print('Здесь должна происходить полезная работа')
    
    @operation
    def another_method(self):
        print('Еще один очень полезный метод')

service = SomeService(operation_=Operation())

# Выведет сначала "Здесь должна происходить полезная работа",
# затем "Операция завершена успешно"
service.some_method()

# Выведет только "Еще один очень полезный метод"
service.another_method()
```

## Счетчик вызовов

В операцию встроен счетчик вызовов. Повторный вход в блок `with` с операцией
после входа не вызовет прогон коллбеков заново:

```python
from classic.operations import Operation, operation

class SomeService:
    
    # Dependency Injection
    def __init__(self, operation_: Operation):
        self.operation_ = operation_

    @operation
    def some_method(self):
        self.another_method()
    
    @operation
    def another_method(self):
        print('Еще один очень полезный метод')

service = SomeService(operation_=Operation())

# Второй вызов operation в этой операции будет пропущен.
service.some_method()
```

## Потокобезопасность

Объект-операция построен на базе `threading.local`, его можно использовать из
разных потоков.

## Декоратор operation

Декоратор operation сделан ради "сахара". Его применение позволяет не писать 
весь код метода на один tab справа, и, вероятно, покроет 95% случаев
использования библиотеки.

Кроме того, декоратор использует `extra_annotations` из classic.components, из-за
этого, при применении декоратора `operation` с components, можно не прописывать
`Operation` в зависимостях:

```python
from classic.components import component
from classic.operations import operation


@component
class SomeService:

    @operation
    def some_method(self):
        print('95% кейс)))')
```

Также можно указать, какое поле у `self` будет использовать декоратор:
```python
from classic.operations import operation


class SomeService:
    
    def __init__(self, read, write, source_repo, target_repo):
        self.read = read
        self.write = write
        self.source_repo = source_repo
        self.target_repo = target_repo

    @operation('read')
    def some_method(self):
        # Представьте себе, что здесь происходит обращение к одной БД,
        # проверка и преобразование данных, и запись одной транзакцией в другую
        some_objects = self.source_repo.load_objects()
        with self.write:
            self.target_repo.write(some_objects)
```

## Отмена операции
Для отмены операции используется исключение Cancel:

```python
from classic.components import component
from classic.operations import operation, Cancel, Operation

@component
class SomeService:
    
    @operation
    def plain_usage(self):
        # после этого исключения class Operation произведет отмену операции, 
        # при этом исключение Cancel будет выброшено наружу 
        raise Cancel
    
    @operation
    def plain_usage_with_suppress(self):
        # Если установить suppress=True, так же произойдет отмена, 
        # но исключение НЕ БУДЕТ выброшено наружу  
        raise Cancel(suppress=True)
    
    @operation
    def class_usage(self):
        # добавлено ради сахара, ведет себя точно так же 
        raise Operation.Cancel

    @operation
    def decorator_usage(self):
        # добавлено ради сахара, ведет себя точно так же
        raise operation.Cancel
    
```

Строго говоря, для отмены операции можно использовать любое исключение. Cancel 
добавлен для возможности подавить распространение исключения.
