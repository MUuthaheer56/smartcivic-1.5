import strawberry
from strawberry.flask.views import GraphQLView
from app.graphql.queries import Query
from app.graphql.mutations import Mutation
from app.graphql.context import get_graphql_context

schema = strawberry.Schema(query=Query, mutation=Mutation)

class SmartCivicGraphQLView(GraphQLView):
    """
    Custom Strawberry GraphQL view that enriches each GraphQL request
    with JWT user authentication context, role claims, and MongoDB instance.
    """
    def get_context(self, request, response):
        ctx = super().get_context(request, response)
        ctx.update(get_graphql_context(request))
        return ctx

