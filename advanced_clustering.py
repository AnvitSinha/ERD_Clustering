import argparse
import os
import numpy as np
import warnings

import nltk
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.cluster import rand_score

from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
from sklearn.preprocessing import normalize

warnings.filterwarnings('ignore')
nltk.download('stopwords', quiet=True)

# Weights for clustering
# Weights for clustering
# TEXT_REL_WEIGHT = 0.1
# TEXT_IDENT_REL_WEIGHT = 0.1
# TEXT_REL_ATTR_WEIGHT = 10.0
# NUM_ENTITY_WEIGHT = 0.1
# NUM_WEAK_ENTITY_WEIGHT = 10.0
# NUM_REL_WEIGHT = 1.0
# NUM_IDENT_REL_WEIGHT = 0.1
# NUM_REL_ATTR_WEIGHT = 0.1
TEXT_REL_WEIGHT = 0.1
TEXT_IDENT_REL_WEIGHT = 0.1
TEXT_REL_ATTR_WEIGHT = 10.0
NUM_ENTITY_WEIGHT = 0.883991316691379
NUM_WEAK_ENTITY_WEIGHT = 1.4291398850822417
NUM_REL_WEIGHT = 3.575283911426867
NUM_IDENT_REL_WEIGHT = 1.5902492310944798
NUM_REL_ATTR_WEIGHT = 1.893584848442421


def get_args() -> argparse.Namespace:
    """Sets the CLI arguments required for the functioning of program"""

    parser = argparse.ArgumentParser()

    parser.add_argument('--dataset_dir', help="Path to directory containing all image information for the dataset"
                        , required=True)
    parser.add_argument('--output_file', help="Path to file where the output should be created", required=True)
    parser.add_argument('--num_clusters', type=int, help="Number of expected clusters", required=True)

    return parser.parse_args()


def get_image_names(dataset_dir: str) -> list[str]:
    """Get the names of all images in the dataset"""

    return os.listdir(dataset_dir)


def create_dataset_json(dataset_dir: str) -> list[dict]:
    """Creates the list of dictionaries that represents each image in the dataset"""

    img_erds = []

    for input_file in os.listdir(dataset_dir):
        with open(os.path.join(dataset_dir, input_file), "r") as inp:
            all_lines = [w.strip().replace('[', '').replace(']', '') for w in inp.readlines()]

            # remove the quotes from each word and remove PK if found since that is not needed
            all_lines = [[w.strip().strip("'") for w in line.split(",") if w.strip().strip("'") != "PK"]
                         for line in all_lines]

        img_erds.append(process_input_file(all_lines))

    return img_erds


def process_input_file(all_lines: list[list[str]]) -> dict:
    """Helper function to create a description of the image with its properties
        gathered from the input file that calls this function"""

    # intialize the dictionary
    img_desc = {
        'num_entity': len(all_lines),
        'num_weak_entity': 0,
        'num_rel': 0,
        'num_ident_rel': 0,
        'num_rel_attr': 0,
        'entity': [],
        'weak_entity': [],
        'rel': [],
        'ident_rel': [],
        'rel_attr': []
    }

    for line in all_lines:

        # process each object

        if line[0] == "entity":
            img_desc['num_entity'] += 1
            img_desc['entity'].extend(line[1:])

        elif line[0] == "weak_entity":
            img_desc['num_weak_entity'] += 1
            img_desc['weak_entity'].extend(line[1:])

        elif line[0] == "rel":
            img_desc['num_rel'] += 1
            img_desc['rel'].extend(line[1:])

        elif line[0] == "rel_attr":
            img_desc['num_rel_attr'] += 1
            img_desc['rel_attr'].extend(line[1:])

        elif line[0] == "ident_rel":
            img_desc['num_ident_rel'] += 1
            img_desc['ident_rel'].extend(line[1:])

    return img_desc


def preprocess_text(text):
    """Helper function to preprocess the text using porter stemmer and nltk stopwords"""
    stemmer = PorterStemmer()
    stop_words = set(stopwords.words('english'))
    words = [stemmer.stem(word) for word in text.split() if word.lower() not in stop_words]
    return ' '.join(words)


def vectorize_text_data(text_data, weight=1.0):
    """Helper function to vectorize a list of text data"""
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(text_data).toarray()
    return tfidf_matrix * weight


def contains_non_empty_strings(arr):
    """Helper function to check if an array contains only empty strings"""
    return any(s.strip() for s in arr)


def get_clusters(img_erds: list[dict], num_clusters: int) -> list[int]:
    """Get the clustering of each image as a list where the index in the clusterings
        corresponds to an image"""

    all_text_rel = []
    all_text_ident_rel = []
    all_text_rel_attr = []
    all_text_entity = []
    all_text_weak_entity = []

    for erd in img_erds:
        all_text_rel.append(preprocess_text(' '.join(erd['rel'])))
        all_text_ident_rel.append(preprocess_text(' '.join(erd['ident_rel'])))
        all_text_rel_attr.append(preprocess_text(' '.join(erd['rel_attr'])))
        all_text_entity.append(preprocess_text(' '.join(erd['entity'])))
        all_text_weak_entity.append(preprocess_text(' '.join(erd['weak_entity'])))

    # Vectorize and cluster with updated weights
    if contains_non_empty_strings(all_text_rel):
        vectorized_text_rel = vectorize_text_data(all_text_rel, TEXT_REL_WEIGHT)
    else:
        vectorized_text_rel = np.array([])

    if contains_non_empty_strings(all_text_ident_rel):
        vectorized_text_ident_rel = vectorize_text_data(all_text_ident_rel, TEXT_IDENT_REL_WEIGHT)
    else:
        vectorized_text_ident_rel = np.array([])

    if contains_non_empty_strings(all_text_rel_attr):
        vectorized_text_rel_attr = vectorize_text_data(all_text_rel_attr, TEXT_REL_ATTR_WEIGHT)
    else:
        vectorized_text_rel_attr = np.array([])

    # Combine the vectors
    combined_vectors = [v for v in
                        [vectorized_text_rel, vectorized_text_ident_rel, vectorized_text_rel_attr]
                        if v.size > 0]

    combined_text_features = np.hstack(combined_vectors) if combined_vectors else np.array([])

    numerical_features = np.array(
        [[erd['num_entity'], erd['num_weak_entity'], erd['num_rel'], erd['num_ident_rel'], erd['num_rel_attr']]
         for erd in img_erds]
    )

    # Normalize numerical features
    normalized_numerical_features = normalize(numerical_features, axis=0)

    weighted_numerical_features = normalized_numerical_features * np.array(
        [NUM_ENTITY_WEIGHT, NUM_WEAK_ENTITY_WEIGHT, NUM_REL_WEIGHT, NUM_IDENT_REL_WEIGHT, NUM_REL_ATTR_WEIGHT]
    )

    features = np.hstack((weighted_numerical_features, combined_text_features))
    # features = np.hstack(weighted_numerical_features)

    # Use Agglomerative cluster assignments as initial centroids for K-Means
    kmeans = KMeans(n_clusters=num_clusters, init="k-means++", n_init=100)
    kmeans.fit(features)

    return kmeans.labels_


def write_output(output_file: str, img_names: list[str], clusters: list[int]):
    """Write to the output file the cluster assignments for each image name
        where each line in the output file corresponds to a cluster"""

    all_lines = [[] for _ in range(max(clusters) + 1)]  # create empty list for each cluster

    for i in range(len(img_names)):
        all_lines[clusters[i]].append(img_names[i].rstrip(".txt"))

    with open(output_file, 'w') as out:
        out.write("\n".join([" ".join(line) for line in all_lines]))


def main():
    # get args
    args = get_args()

    # get image names
    img_names = get_image_names(args.dataset_dir)

    # get image dataset as dictionary
    img_erds = create_dataset_json(args.dataset_dir)

    # get clusterings
    clusters = get_clusters(img_erds, args.num_clusters)

    # write output
    write_output(args.output_file, img_names, clusters)


if __name__ == '__main__':
    main()
