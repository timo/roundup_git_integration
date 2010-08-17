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
# correctly set in roundup.

usermap = {"":""
        ,"Timo Paulssen": "timo"
       #,"Person Two": "otheruser"
       #,"Person Three": "thirduser"
    }

import sys
from subprocess import Popen, PIPE
import roundup.instance, roundup.date

def call_output(*args, **kwargs):
    po = Popen(*args, stdout=PIPE, **kwargs)
    return po.stdout.read()

def commits_from_revs(old, new):
    output = call_output(["git", "log", 
                          '--format=%H%n%h%n%aN%n%aE%n%s%n%b%n.%n%n',
                          "%s..%s" % (old, new)])
    return output.split("\n.\n\n\n")

def number_from_ident(oident):
    ident = oident
    while not ident.isdigit() and ident:
        ident = ident[1:]
    if not ident:
        raise ValueError("%s is not a valid identifier" % oident)
    return ident


class CouldNotIdentifyError(Exception):
    pass


class Identifier(object):
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
        for ident in cls.identifiers.itervalues():
            ident.identify(db)

def act_on_commits(commits):
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
            if not line.startswith("Issue"):
                bodylines.append(line)
            else:
                actions.append(line)

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
            user = task["author"]
            db = tracker.open(user.username)

            issue_id = number_from_ident(task["issue"])

            message_id = db.msg.create(author=user.userid, 
                                    content=task["body"],
                                    date=roundup.date.Date())
            db.issue.set(issue_id, messages=db.issue.get(issue_id, "messages") + [message_id])
            
            if task["setstatus"]:
                try:
                    status_id = db.status.lookup(task["setstatus"])
                    db.issue.set(issue_id, status=status_id)
                except KeyError, e:
                    print >> sys.stderr, (
                        "Could not set the status of %s to %s (%r)"
                        % (task["issue"], task["setstatus"], e))

            db.commit()
            db.close()

if __name__ == "__main__":
    oldrev, newrev, refname = sys.argv[-3:]
    act_on_commits(commits_from_revs(oldrev, newrev))
