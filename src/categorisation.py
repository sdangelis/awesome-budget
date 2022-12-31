"""
ML model to categorise tranasctions and related functions
"""

from os import path

import pandas as pd
from joblib import dump, load
from sklearn.base import ClassifierMixin
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import PassiveAggressiveClassifier

categories = {
    "Entertainment": 1,
    "Food and Drink": 2,
    "Groceries": 3,
    "Shopping": 4,
    "Health": 5,
    "Savings and investments": 6,
    "Transport and Travel": 7,
    "Housing, Taxes and Utilities": 8,
    "Transfers": 9,
    "Subscriptions and services": 10,
    "Other": 11,
}


def init_model(
    vectorizer: HashingVectorizer,
    training_corpus: path = path.join("data/"),
    classes: dict = categories.copy(),
) -> PassiveAggressiveClassifier:
    """
    Initialise model with training_corpus

    :param vectorizer: Vectorizer object to use 
    :param training_corpus: path to, defaults to 
    :param classes: defaults to Categories
    :returns: the model 
    """
    data = pd.read_json(training_corpus).reset_index(drop=False)
    corpus = data.iloc[:, 0]
    y = data.iloc[:, 1]

    return fit_batch(corpus, y, classes, vectorizer)


def fit_batch(
    X: pd.Series,
    y: pd.Series,
    classes: dict,
    vectorizer: HashingVectorizer = HashingVectorizer(n_features=2 ** 18),
) -> PassiveAggressiveClassifier:
    """
    Fits the classifier on a new batch of data 

    :param X: series of strings to vectorize
    :param y: series of category lables for X
    :param traning_corpus: path to Json file with training corpus as text:category
    :param classes: {category_name:category_id} dictionary with all categories. 
    """
    # Fit vectoriser
    X = vectorizer.fit_transform(X)

    classifier = PassiveAggressiveClassifier()
    classifier = classifier.partial_fit(X, y, classes=classes.values())
    return classifier


def serialise_model(
    model: ClassifierMixin, vectorizer: HashingVectorizer, dir: path
) -> bool:
    """
    Saves model and vectorizer to file. 

    :param model: skleran model to save
    :param vectorizer: vectorizer to save - this is purely a convenience as 
    HashingVectorizer are stateless 
    :param dir: directory to save the classifier.joblib and filename.joblib files in
    :returns: True if successful
    """
    dump(model, path.join(dir, "classifier.joblib"))
    dump(vectorizer, path.join(dir, "vectorizer.joblib"))
    return True


def load_model(dir: path) -> tuple:
    """
    Saves model and vectorizer from file. 

    :param dir: directory to load the classifier.joblib and filename.joblib files from
    :returns: a tuple with (model, vectorizer)
    """
    model = load(path.join(dir, "classifier.joblib"))
    vectorizer = load(path.join(dir, "vectorizer.joblib"))
    return (model, vectorizer)
