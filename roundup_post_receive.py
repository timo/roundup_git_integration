#!/usr/bin/python
#
# this hook understands the following syntax in commit messages:
# IssueN [<new status>]

##################################
###
### configuration
###

## tracker_home
# where your roundup tracker home lies
# this will probably be an absolute path

tracker_home = "./demo"



## usermap
# maps from git commiter name to roundup user name
# you only have to use this if the users don't have their full name
# or email address correctly set in roundup.

usermap = {"":""
        ,"Timo Paulssen": "timo"
       #,"Person Two": "otheruser"
       #,"Person Three": "thirduser"
    }

import sys
from subprocess import Popen, PIPE
import roundup.instance, roundup.date

def call_output(*args, **kwargs):
    """Call an external program and return the output from stdout."""
    kwargs.update(stdout=PIPE)
    po = Popen(*args, **kwargs)
    return po.stdout.read()

def commits_from_revs(old, new):
    """Get all commits from `old` to `new`.

    The format of the commits returned is this:
    [complete hash, abbreviated hash, 
     author fullname, author email,
     body of the message]"""
    output = call_output(["git", "log", 
                          '--pretty=format:%H%n%h%n%aN%n%ae%n%s%n%b%n.%n%n',
                          "%s..%s" % (old, new)])
    if output.endswith("\n.\n\n\n"):
        output = output[:-len("\n.\n\n\n")]
    return output.split("\n.\n\n\n")

def number_from_ident(oident):
    """Get the number of an identifier.

    For instance, turn Issue42 into just 42"""
    ident = oident
    while not ident.isdigit() and ident:
        ident = ident[1:]
    if not ident:
        raise ValueError("%s is not a valid identifier" % oident)
    return ident


class CouldNotIdentifyError(Exception):
    """The user could not be found in the usermap, or the roundup database."""
    pass


class Identifier(object):
    """Identifies a user.
    
    Use Identifier.make(name, mail) to get an instance."""
    identifiers = {}
    def __init__(self, name, mail):
        self.name = name
        self.mail = mail
        self.username = None
        self.userid = None
        self.identifiers[(name, mail)] = self

    def __str__(self):
        return "(name=%s, mail=%s)" % (self.name, self.mail)

    def __repr__(self):
        return "(name=%s, mail=%s)" % (self.name, self.mail)

    @classmethod
    def make(cls, name, mail):
        """Get an identifier object for the user."""
        if (name, mail) in cls.identifiers:
            return cls.identifiers[(name, mail)]
        else:
            return cls(name, mail)

    def identify(self, db):
        if self.name in usermap:
            self.username = usermap[self.name]
            self.userid = db.user.lookup(self.username)
        else:
            candidates = db.user.filter(db.user.list(), 
                                        {"realname": self.name})
            if len(candidates) == 1:
                self.userid = candidates[0]
            else:
                candidates = db.user.filter(db.user.list(), 
                                            {"address": self.mail})
                if len(candidates) == 1:
                    self.userid = candidates[0]
                else:
                    raise CouldNotIdentifyError("Could not find user %r in"
                            "usermap or by realname or email (%r) in roundup."
                            % (self.name, self.mail))

            self.username = db.user.get(self.userid, "username")

    @classmethod
    def identify_all(cls, db):
        """Identifies all identifiers in the system using the database.

        The database should be opened as admin, so that the
        permissions are OK."""
        for ident in cls.identifiers.itervalues():
            try:
                ident.identify(db)
            except CouldNotIdentifyError, e:
                print >> sys.stderr, e

def execute_task(tracker, task):
    """Execute the task on the tracker.

    The task is a dictionary with the format:
    {"author": Identifier instance (already identified),
     "issue": roundup identifier of the issue (for instance "Issue23"),
     "body": the body of the commit message from git.,
     "setstatus": None or the name of the status to set (for instance "resolved")
    }

    If the db is already open at this point, the hook will deadlock.
    """
    user = task["author"]
    if not user.username:
        print >> sys.stderr, ("skipping task on %s for user %r"
                % (task["issue"], task["author"]))
        return False
    try:
        db = tracker.open(user.username)
    except Exception, e:
        print >> sys.stderr, (
          "While trying to act on behalf of %r (roundup user %s): %r" %
            (user, user.username, e))
        return False

    issue_id = number_from_ident(task["issue"])

    try:
        message_id = db.msg.create(author=user.userid,
                                   content=task["body"],
                                   date=roundup.date.Date())

        db.issue.set(issue_id, messages=db.issue.get(issue_id, "messages") + [message_id])
    except Exception, e:
        print >> sys.stderr, (
          "While trying to create the message on %s for user %r "
          "(roundup user %s): %r" %
            (task["issue"], user, user.username, e))
        db.rollback()
        db.close()
        return False

    if task["setstatus"]:
        try:
            status_id = db.status.lookup(task["setstatus"])
            db.issue.set(issue_id, status=status_id)
        except KeyError, e:
            print >> sys.stderr, (
                "Could not set the status of %s to %s (%r)"
                % (task["issue"], task["setstatus"], e))

            # we could rollback here, but this is non-critical.

    db.commit()
    db.close()

    return True


def act_on_commits(commits):
    """Go through all commits and execute the necessary actions."""
    todo = []
    idents = []
    for commit in commits:
        parts = commit.split("\n")
        parts.reverse()
        if len(parts) < 3:
            continue

        chash = parts.pop()
        cid = parts.pop()
        author = parts.pop()
        email = parts.pop()
        parts.reverse()
        messagelines = parts

        ident = Identifier.make(author, email)

        bodylines = []
        actions = []
        for line in messagelines:
            if line.startswith("Issue") and line[len("Issue"):line.find(" ")].isdigit():
                actions.append(line)
            else:
                bodylines.append(line)

        if actions:
            body = "git:%s referenced this issue:\n%s" % (cid, "\n".join(bodylines))
            for action in actions:
                parts = action.split(" ")

                tododict = dict(author=ident, setstatus=None)

                if len(parts) > 1:
                    issue, newstatus = parts
                    tododict.update(setstatus=newstatus, body=body + "\n" + action)
                else:
                    issue = parts[0]
                    tododict.update(body=body)

                tododict.update(issue=issue)

                todo.append(tododict)


    if todo:
        print todo
        tracker = roundup.instance.open(tracker_home)

        db = tracker.open("admin")
        Identifier.identify_all(db)
        db.close()

        for task in todo:
            execute_task(tracker, task)


if __name__ == "__main__":
    oldrev, newrev, refname = sys.stdin.readline().split(" ")[-3:]
    act_on_commits(commits_from_revs(oldrev, newrev))
