import os, nltk
import networkx as nx
from operator import itemgetter
from pymongo import MongoClient



def remove_gutenberg_meta_data(text):
	start = text.find('START OF THIS PROJECT GUTENBERG EBOOK')
	end = text.find('END OF THIS PROJECT GUTENBERG EBOOK')

	if start != -1 and end != -1:
		start = text.find('\n', start)
		if start != -1 and start < end:
			return text[start:end].replace('_', '')
		else:
			return text
	else:
		return text


def tag_texts(mongo_results):
	#text = 'The President invited Andrea and Reijo Nikolov to his house.'
	tagged_texts = []
	for result in mongo_results:
		text = remove_gutenberg_meta_data(result['text'])
		sentences = nltk.sent_tokenize(text)
		words = [nltk.word_tokenize(sentence) for sentence in sentences]
		tagged_words = [nltk.pos_tag(sentence) for sentence in words]
		tagged_texts.append(tagged_words)
	return tagged_texts


def find_people(tagged_texts):
	def extract_people(t):
		people = set()
		if hasattr(t, 'label') and t.label is not None:
			if t.label() == 'PERSON':
				person = ' '.join([child[0] for child in t if len(child) > 1 and child[1] == 'NNP'])
				person = person.strip()
				if person != '':
					people.add(person)
			else:
				for child in t:
					people.update(extract_people(child))
		return people

	chars = set()
	for text in tagged_texts:
		chunks = nltk.ne_chunk_sents(text, binary=False)
		for tree in chunks:
			chars.update(extract_people(tree))
	return chars


def transform_tagged_text(tagged_text):
	def transform_tree(t, tokens):
		if hasattr(t, 'label') and t.label is not None:
			if t.label() == 'PERSON':
				token = ' '.join([child[0] for child in t if len(child) > 1 and child[1] == 'NNP'])
				token = token.strip()
				if token != '':
					tokens.append(token)
			else:
				for child in t:
					transform_tree(child, tokens)
		else:
			token = t[0].strip()
			if token != '':
				tokens.append(token)

	chunks = nltk.ne_chunk_sents(tagged_text, binary=False)
	tokens = []
	for tree in chunks:
		transform_tree(tree, tokens)
	return tokens


def count_char_occur(tagged_texts, characters):
	counts = {char: 0 for char in characters}
	for text in tagged_texts:
		text_new = transform_tagged_text(text)
		for token in text_new:
			if token in characters:
				counts[token] += 1
	return counts


def create_network(tagged_texts, characters, N=15):
	network = {}
	
	# initialize the network
	for char1 in characters:
		for char2 in characters:
			if char1 != char2:
				if char1 not in network:
					network[char1] = {}
				if char2 not in network[char1]:
					network[char1][char2] = 0
				if char2 not in network:
					network[char2] = {}
				if char1 not in network[char2]:
					network[char2][char1] = 0

	for text in tagged_texts:
		tokens = transform_tagged_text(text)
		
		# process the first window in the book, filling in the list of characters in the current window
		curr_chars = {}
		window = tokens[:N]
		for i in range(len(window)):
			if window[i] in characters:
				curr_chars[window[i]] = i + 1

		# if there are more than 1 characters already, add links to them in the network
		if len(curr_chars) > 1:
			for char1 in curr_chars.keys():
				for char2 in curr_chars.keys():
					if char1 != char2:
						network[char1][char2] += 1
						network[char2][char1] += 1

		for i in range(N, len(tokens)):
			# remove characters outside of the window
			curr_char_names = list(curr_chars.keys())
			for char in curr_char_names:
				if curr_chars[char] == 1:
					del curr_chars[char]
				else:
					curr_chars[char] -= 1

			# if the token is a character, add it to the list
			token = tokens[i]
			if token in characters:
				for char in curr_chars.keys():
					if char != token:
						network[char][token] += 1
						network[token][char] += 1
				curr_chars[token] = N

	# make networkx graph
	G = nx.Graph()
	for char1 in network.keys():
		for char2 in network[char1].keys():
			if network[char1][char2] > 0:
				if char1 not in G or (char1 in G and char2 not in G.neighbors(char1)):
					G.add_edge(char1, char2, weight=network[char1][char2])

	# only used the largest connected component
	lcc = nx.Graph(max(nx.connected_component_subgraphs(G), key=len))
	return lcc


def insert_or_replace_doc(filepath):
	title = os.path.splitext(os.path.basename(filepath))[0].lower()
	with open(filepath, 'r') as f:
		text = f.read()

	mongodb = MongoClient()
	db = mongodb.projectB
	mongo_results = db.books.find({'title': title})
	if mongo_results.count() > 0:
		db.books.replace_one({'title': title}, {'title': title, 'text': text})
	else:
		db.books.insert_one({'title': title, 'text': text})


def insert_texts_to_mongodb(dirpath):
	if not os.path.exists(dirpath):
		raise ValueError('The directory you specified does not exist: %s. Make sure you entered the Python shell from inside your project directory, ~/Projects/book-project.' % dirpath)

	if os.path.isfile(dirpath):
		if os.path.splitext(dirpath)[1].lower() == '.txt':
			insert_or_replace_doc(dirpath)
		else:
			raise ValueError('You supplied the name of a file that does not have the .txt extension. Please, either specify a .txt file, or a folder containing .txt files as the argument for this function.')
	else:
		files = os.listdir(dirpath)
		txt_found = False
		for f in files:
			if os.path.splitext(f)[1].lower() == '.txt':
				txt_found = True
				insert_or_replace_doc(os.path.join(dirpath, f))

		if not txt_found:
			raise ValueError('Not .txt files were found in the directory you provided as an argument.')
	
if __name__ == '__main__':
	print('This file is meant to be imported into other code, not to be run directly.')
	
