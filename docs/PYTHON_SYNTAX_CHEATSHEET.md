# 🐍 Python Syntax Cheat Sheet

Quick reference guide for Python syntax and common patterns.

---

## 📝 Table of Contents
1. [Variables & Data Types](#variables--data-types)
2. [Operators](#operators)
3. [Strings](#strings)
4. [Lists & Collections](#lists--collections)
5. [Control Flow](#control-flow)
6. [Functions](#functions)
7. [Classes & Objects](#classes--objects)
8. [File Operations](#file-operations)
9. [Error Handling](#error-handling)
10. [Imports & Modules](#imports--modules)
11. [List Comprehensions](#list-comprehensions)
12. [Decorators](#decorators)
13. [Common Patterns](#common-patterns)

---

## 🔢 Variables & Data Types

```python
# Basic types
name = "John"              # str (string)
age = 25                   # int (integer)
price = 19.99             # float (floating point)
is_active = True          # bool (boolean)
data = None               # NoneType

# Type hints (optional, but recommended)
name: str = "John"
age: int = 25
price: float = 19.99
is_active: bool = True

# Multiple assignment
x, y, z = 1, 2, 3
a = b = c = 0

# Type conversion
num_str = "42"
num_int = int(num_str)      # Convert to integer
num_float = float(num_str)  # Convert to float
str_num = str(42)           # Convert to string
```

---

## 🔧 Operators

```python
# Arithmetic
a + b    # Addition
a - b    # Subtraction
a * b    # Multiplication
a / b    # Division (returns float)
a // b   # Floor division (returns int)
a % b    # Modulo (remainder)
a ** b   # Exponentiation (power)

# Comparison
a == b   # Equal to
a != b   # Not equal to
a < b    # Less than
a > b    # Greater than
a <= b   # Less than or equal
a >= b   # Greater than or equal

# Logical
a and b  # Logical AND
a or b   # Logical OR
not a    # Logical NOT

# Identity
a is b       # Same object (identity)
a is not b   # Different objects

# Membership
x in list    # Check if x is in list
x not in list

# Assignment operators
a += 1   # a = a + 1
a -= 1   # a = a - 1
a *= 2   # a = a * 2
a /= 2   # a = a / 2
```

---

## 📄 Strings

```python
# Basic string operations
text = "Hello"
text = 'Hello'
text = """Multi-line
string"""

# String methods
text.upper()              # "HELLO"
text.lower()              # "hello"
text.strip()              # Remove whitespace
text.replace("l", "L")    # "HeLLo"
text.split(",")           # Split by delimiter
",".join(["a", "b"])      # "a,b"

# String formatting (3 ways)
# 1. f-strings (Python 3.6+, recommended)
name = "John"
age = 25
message = f"My name is {name} and I'm {age} years old"

# 2. .format()
message = "My name is {} and I'm {} years old".format(name, age)
message = "My name is {name} and I'm {age} years old".format(name=name, age=age)

# 3. % formatting (old style)
message = "My name is %s and I'm %d years old" % (name, age)

# String slicing
text = "Hello World"
text[0]        # "H" (first character)
text[-1]       # "d" (last character)
text[0:5]      # "Hello" (slice from 0 to 5)
text[:5]       # "Hello" (from start to 5)
text[6:]       # "World" (from 6 to end)
text[::-1]     # "dlroW olleH" (reverse)
```

---

## 📋 Lists & Collections

### Lists
```python
# Create lists
my_list = [1, 2, 3]
my_list = list(range(5))  # [0, 1, 2, 3, 4]

# Access elements
my_list[0]        # First element
my_list[-1]       # Last element
my_list[1:3]      # Slice [2, 3]

# Modify lists
my_list.append(4)           # Add to end
my_list.insert(0, 0)        # Insert at index
my_list.extend([5, 6])      # Add multiple
my_list.remove(2)           # Remove value
my_list.pop()               # Remove and return last
my_list.pop(0)              # Remove and return at index
del my_list[0]              # Delete by index

# List methods
len(my_list)                # Length
my_list.count(2)            # Count occurrences
my_list.index(3)            # Find index
my_list.sort()              # Sort in place
sorted(my_list)             # Return sorted copy
my_list.reverse()           # Reverse in place
```

### Tuples
```python
# Tuples are immutable
my_tuple = (1, 2, 3)
my_tuple = 1, 2, 3          # Parentheses optional
a, b, c = my_tuple          # Unpacking
```

### Dictionaries
```python
# Create dictionaries
my_dict = {"name": "John", "age": 25}
my_dict = dict(name="John", age=25)

# Access
my_dict["name"]             # "John"
my_dict.get("name")         # "John" (safe, returns None if missing)
my_dict.get("name", "N/A")  # "John" (with default)

# Modify
my_dict["city"] = "NYC"     # Add/update
my_dict.update({"age": 26}) # Update multiple
del my_dict["age"]          # Delete key
my_dict.pop("age")          # Remove and return value

# Iterate
for key in my_dict:         # Iterate keys
for key, value in my_dict.items():  # Iterate key-value pairs
for value in my_dict.values():      # Iterate values
```

### Sets
```python
# Sets store unique values
my_set = {1, 2, 3}
my_set = set([1, 2, 3])

# Set operations
my_set.add(4)               # Add element
my_set.remove(2)            # Remove (error if missing)
my_set.discard(2)           # Remove (no error if missing)
set1 | set2                 # Union
set1 & set2                 # Intersection
set1 - set2                 # Difference
```

---

## 🔀 Control Flow

### If/Else
```python
if condition:
    do_something()
elif other_condition:
    do_something_else()
else:
    do_default()

# Ternary operator
result = "yes" if condition else "no"

# Multiple conditions
if x > 0 and y > 0:
    pass
if x > 0 or y > 0:
    pass
```

### For Loops
```python
# Iterate over list
for item in my_list:
    print(item)

# With index
for index, item in enumerate(my_list):
    print(f"{index}: {item}")

# Range
for i in range(5):          # 0, 1, 2, 3, 4
    print(i)

for i in range(1, 6):       # 1, 2, 3, 4, 5
    print(i)

for i in range(0, 10, 2):   # 0, 2, 4, 6, 8 (step by 2)
    print(i)

# Iterate dictionary
for key, value in my_dict.items():
    print(f"{key}: {value}")
```

### While Loops
```python
while condition:
    do_something()
    if break_condition:
        break
    if skip_condition:
        continue
```

### Break & Continue
```python
for item in my_list:
    if item == "skip":
        continue    # Skip to next iteration
    if item == "stop":
        break       # Exit loop
    print(item)
```

---

## 🔨 Functions

```python
# Basic function
def greet(name):
    return f"Hello, {name}!"

# With default arguments
def greet(name, greeting="Hello"):
    return f"{greeting}, {name}!"

# With type hints
def add(a: int, b: int) -> int:
    return a + b

# Multiple arguments
def sum_all(*args):         # Variable positional args
    return sum(args)

def print_info(**kwargs):   # Variable keyword args
    for key, value in kwargs.items():
        print(f"{key}: {value}")

# Lambda (anonymous functions)
square = lambda x: x ** 2
add = lambda a, b: a + b

# Used with map, filter
numbers = [1, 2, 3, 4]
squared = list(map(lambda x: x**2, numbers))  # [1, 4, 9, 16]
evens = list(filter(lambda x: x % 2 == 0, numbers))  # [2, 4]
```

---

## 🏗️ Classes & Objects

```python
# Basic class
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
    
    def greet(self):
        return f"Hello, I'm {self.name}"

# Usage
person = Person("John", 25)
person.greet()

# Class with type hints
class Person:
    def __init__(self, name: str, age: int):
        self.name: str = name
        self.age: int = age

# Inheritance
class Student(Person):
    def __init__(self, name, age, student_id):
        super().__init__(name, age)
        self.student_id = student_id

# Class methods and static methods
class MyClass:
    class_var = "shared"
    
    @classmethod
    def class_method(cls):
        return cls.class_var
    
    @staticmethod
    def static_method():
        return "No self or cls needed"
```

---

## 📁 File Operations

```python
# Read file
with open("file.txt", "r") as f:
    content = f.read()          # Read entire file
    lines = f.readlines()       # Read all lines
    line = f.readline()          # Read one line

# Write file
with open("file.txt", "w") as f:
    f.write("Hello World")

# Append to file
with open("file.txt", "a") as f:
    f.write("New line\n")

# Read line by line (memory efficient)
with open("file.txt", "r") as f:
    for line in f:
        print(line.strip())

# File modes
# "r"  - Read (default)
# "w"  - Write (overwrites)
# "a"  - Append
# "x"  - Exclusive creation
# "b"  - Binary mode
# "t"  - Text mode (default)
# "+"  - Read and write
```

---

## ⚠️ Error Handling

```python
# Try/Except
try:
    result = 10 / 0
except ZeroDivisionError:
    print("Cannot divide by zero")
except ValueError as e:
    print(f"Value error: {e}")
except Exception as e:
    print(f"Error: {e}")
else:
    print("No errors occurred")
finally:
    print("Always executes")

# Raise exceptions
if value < 0:
    raise ValueError("Value must be positive")

# Custom exceptions
class CustomError(Exception):
    pass

raise CustomError("Something went wrong")
```

---

## 📦 Imports & Modules

```python
# Standard imports
import os
import sys
from pathlib import Path

# Import with alias
import numpy as np
import pandas as pd

# Import specific items
from datetime import datetime, timedelta

# Import all (not recommended)
from module import *

# Conditional imports
try:
    import optional_module
except ImportError:
    optional_module = None

# Check if running as script
if __name__ == "__main__":
    # Code here only runs when file is executed directly
    # Not when imported as a module
    main()
```

---

## 🎯 List Comprehensions

```python
# Basic list comprehension
squares = [x**2 for x in range(10)]

# With condition
evens = [x for x in range(10) if x % 2 == 0]

# Nested
matrix = [[i*j for j in range(3)] for i in range(3)]

# Dictionary comprehension
squares_dict = {x: x**2 for x in range(5)}

# Set comprehension
unique_squares = {x**2 for x in range(10)}

# Generator expression (memory efficient)
squares_gen = (x**2 for x in range(10))
```

---

## 🎨 Decorators

```python
# Basic decorator
def my_decorator(func):
    def wrapper(*args, **kwargs):
        print("Before function")
        result = func(*args, **kwargs)
        print("After function")
        return result
    return wrapper

@my_decorator
def greet(name):
    return f"Hello, {name}!"

# Decorator with arguments
def repeat(times):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for _ in range(times):
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator

@repeat(3)
def say_hello():
    print("Hello!")

# Built-in decorators
@property
@staticmethod
@classmethod
@functools.lru_cache  # Memoization
```

---

## 🔧 Common Patterns

### Context Managers
```python
# Using with statement
with open("file.txt") as f:
    content = f.read()

# Custom context manager
from contextlib import contextmanager

@contextmanager
def my_context():
    print("Entering")
    yield
    print("Exiting")
```

### Enumerate
```python
items = ["a", "b", "c"]
for index, item in enumerate(items):
    print(f"{index}: {item}")

# Start from different number
for index, item in enumerate(items, start=1):
    print(f"{index}: {item}")
```

### Zip
```python
names = ["Alice", "Bob", "Charlie"]
ages = [25, 30, 35]

for name, age in zip(names, ages):
    print(f"{name} is {age}")

# Unzip
pairs = list(zip(names, ages))
names, ages = zip(*pairs)
```

### Any & All
```python
numbers = [1, 2, 3, 4, 5]
any(x > 3 for x in numbers)  # True (at least one)
all(x > 0 for x in numbers)  # True (all are)
```

### Walrus Operator (Python 3.8+)
```python
# Assign and check in one line
if (n := len(my_list)) > 10:
    print(f"List has {n} items")

# In while loop
while (line := file.readline()) != "":
    process(line)
```

### Match/Case (Python 3.10+)
```python
match value:
    case 1:
        print("One")
    case 2 | 3:
        print("Two or three")
    case x if x > 10:
        print("Greater than 10")
    case _:
        print("Default")
```

---

## 📚 Useful Built-in Functions

```python
# Type checking
type(obj)                    # Get type
isinstance(obj, int)         # Check type
hasattr(obj, 'attr')         # Check if has attribute

# Math
abs(-5)                      # 5
max(1, 2, 3)                 # 3
min(1, 2, 3)                 # 1
sum([1, 2, 3])               # 6
round(3.14159, 2)            # 3.14

# Collections
len([1, 2, 3])               # 3
sorted([3, 1, 2])            # [1, 2, 3]
reversed([1, 2, 3])          # Iterator
all([True, True, False])     # False
any([True, False, False])    # True

# String/Number conversion
str(42)                      # "42"
int("42")                    # 42
float("3.14")                # 3.14
bool(1)                      # True

# Iterables
range(5)                     # 0, 1, 2, 3, 4
enumerate(list)              # (0, item0), (1, item1), ...
zip(list1, list2)            # Pairs items
```

---

## 🎓 Quick Tips

1. **Indentation matters!** Python uses indentation instead of braces
2. **Use `==` for equality, `is` for identity**
3. **f-strings are preferred** over `.format()` or `%`
4. **Use `with` statements** for file operations
5. **List comprehensions** are more Pythonic than loops
6. **Type hints** improve code readability
7. **Docstrings** document functions: `"""Description"""`

---

## 📖 Common Python Idioms

```python
# Swap variables
a, b = b, a

# Check if list is empty
if not my_list:
    print("Empty")

# Default dictionary value
value = my_dict.get("key", "default")

# Multiple return values
def get_name_age():
    return "John", 25

name, age = get_name_age()

# Chained comparisons
if 0 < x < 10:
    pass

# Slice assignment
my_list[1:3] = [10, 20]
```

---

**Happy Coding! 🚀**




