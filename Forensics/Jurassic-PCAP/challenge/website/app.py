from flask import Flask, render_template

app = Flask(__name__)


DINOSAURS = [
    {
        "name": "Allosaurus",
        "kind": "THE TOP PREDATOR",
        "period": "Late Jurassic · about 155–145 million years ago",
        "image": "images/allosaurus.jpg",
        "alt": "Fossilized Allosaurus skull and vertebrae against a black background.",
        "class": "card--wide",
    },
    {
        "name": "Stegosaurus",
        "kind": "THE PLATED ONE",
        "period": "Late Jurassic · about 155–150 million years ago",
        "image": "images/stegosaurus.jpg",
        "alt": "Mounted Stegosaurus skeleton with its back plates on display beside a person for scale.",
        "class": "",
    },
    {
        "name": "Brachiosaurus",
        "kind": "THE TALL ONE",
        "period": "Late Jurassic · about 154–150 million years ago",
        "image": "images/brachiosaurus.jpg",
        "alt": "Mounted Brachiosaurus skeleton rising through a bright museum hall.",
        "class": "",
    },
    {
        "name": "Diplodocus",
        "kind": "THE LONG ONE",
        "period": "Late Jurassic · about 154–152 million years ago",
        "image": "images/diplodocus.jpg",
        "alt": "Long Diplodocus skeleton spanning a dim museum hall, with visitors beneath it.",
        "class": "",
    },
    {
        "name": "Archaeopteryx",
        "kind": "THE FEATHERED ONE",
        "period": "Late Jurassic · about 150 million years ago",
        "image": "images/archaeopteryx.jpg",
        "alt": "Mounted Archaeopteryx skeleton displayed with its wings outstretched.",
        "class": "card--wide",
    },
    {
        "name": "Compsognathus",
        "kind": "THE LITTLE ONE",
        "period": "Late Jurassic · about 150 million years ago",
        "image": "images/compsognathus.jpg",
        "alt": "Illustration of a Compsognathus fossil skeleton preserved on a stone slab.",
        "class": "",
    },
]


@app.route("/")
def gallery():
    return render_template("index.html", dinosaurs=DINOSAURS)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
