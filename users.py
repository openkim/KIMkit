class User:
    """
    Class used to manage users of KIMkit
    """

    def __init__(self):
        self.UUID = self._generate_UUID()
        self.developer_of = []
        self.contributor_of = []
        self.maintainer_of = []

    def _generate_UUID(self):
        pass

    def make_developer_of(kimID):
        pass

    def make_contributor_of(kimID):
        pass

    def make_maintainer_of(kimID):
        pass


def delete_user(UUID):
    pass


def get_developers_of(kimID):
    pass


def get_contributors_of(kimID):
    pass


def get_maintainers_of(kimID):
    pass
