def internal_function(value):
    return value + 100


class InternalWidget:
    def __init__(self, size):
        self.size = size

    def run(self):
        return self.size * 2
