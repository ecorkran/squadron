"""GraphQL documents sent to GitHub.

Split out of ``github_cli.py`` per the task breakdown: the queries are a
cohesive unit that changes for its own reasons — a field GitHub adds, renames,
or deprecates — separately from the transport and classification around them.

Field names here are pinned against captured responses in
``tests/codehost/fixtures/gh/``, not written from memory.
"""

from __future__ import annotations

#: Fields a resolved pull request needs. ``baseRefOid`` is what makes the
#: post-fetch "base moved since resolution" check exact rather than heuristic.
PR_QUERY = """
query($owner:String!,$name:String!,$number:Int!){
  repository(owner:$owner,name:$name){
    pullRequest(number:$number){
      number url title body state author{login}
      baseRefName baseRefOid headRefName headRefOid
      isCrossRepository headRepository{nameWithOwner}
      closingIssuesReferences(first:20){nodes{number}}
    }
  }
}
"""

#: ``first:2`` is deliberate: it distinguishes one open PR from many without
#: paying for a second page.
PR_FOR_BRANCH_QUERY = """
query($owner:String!,$name:String!,$branch:String!){
  repository(owner:$owner,name:$name){
    pullRequests(headRefName:$branch,states:OPEN,first:2){nodes{number}}
  }
}
"""

#: Paged by the caller, bounded by ``MAX_DISCUSSION_PAGES``.
REVIEW_THREADS_QUERY = """
query($owner:String!,$name:String!,$number:Int!,$cursor:String){
  repository(owner:$owner,name:$name){
    pullRequest(number:$number){
      reviewThreads(first:100,after:$cursor){
        pageInfo{hasNextPage endCursor}
        nodes{isResolved comments(first:1){nodes{path line author{login} body url}}}
      }
    }
  }
}
"""
