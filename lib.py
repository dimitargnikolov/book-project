import os, nltk
import networkx as nx
from operator import itemgetter


def load_text(filepath):
	with open(filepath, 'r') as f:
		text = f.read()
	#text = 'The President invited Andrea and Reijo Nikolov to his house.'
	sentences = nltk.sent_tokenize(text)
	words = [nltk.word_tokenize(sentence) for sentence in sentences]
	tagged_words = [nltk.pos_tag(sentence) for sentence in words]
	return tagged_words


def find_characters(tagged_words):
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

	chunks = nltk.ne_chunk_sents(tagged_words, binary=False)
	chars = set()
	for tree in chunks:
		chars.update(extract_people(tree))
	return chars


def transform_book(tagged_words):
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

	chunks = nltk.ne_chunk_sents(tagged_words, binary=False)
	tokens = []
	for tree in chunks:
		transform_tree(tree, tokens)
	return tokens


def count_char_occur(book, characters):
	counts = {char: 0 for char in characters}
	book_new = transform_book(book)
	for token in book_new:
		if token in characters:
			counts[token] += 1
	return counts


def create_network(book, characters, max_distance=15):
	network = {}
	tokens = transform_book(book)
	
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

	# process the first window in the book, filling in the list of characters in the current window
	curr_chars = {}
	window = tokens[:max_distance]
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
					
	for i in range(max_distance, len(tokens)):
		# remove characters outside of the window
		curr_char_names = curr_chars.keys()
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
			curr_chars[token] = max_distance

	# make networkx graph
	G = nx.Graph()
	for char1 in network.keys():
		for char2 in network[char1].keys():
			if network[char1][char2] > 0:
				if char1 not in G or (char1 in G and char2 not in G.neighbors(char1)):
					G.add_edge(char1, char2, weight=network[char1][char2])
					
	return G


if __name__ == '__main__':
	print('Reading book.')
	book = load_text(os.path.join('data', 'alice.txt'))

	print('Finding characters.')
	chars = find_characters(book)

	chars.remove('Which')
	chars.remove('Project Gutenberg')
	chars.remove('Project Gutenberg-tm')
	chars.remove('Him')
	chars.remove('Down')
	chars.remove('Salt Lake City')
	chars.remove('Lewis Carroll')
	chars.remove('Release Date')
	chars.remove('Lewis Carroll THE')
	chars.remove('Geography')
	chars.remove('Project')
	chars.remove('Beautiful')
	chars.remove('Between')
	chars.remove('Character')
	chars.remove('Has')
	
	print('Computing counts.')
	char_counts = count_char_occur(book, chars)
	
	sorted_counts = sorted(char_counts.items(), key=itemgetter(1), reverse=True)
	print(sorted_counts)

	print('Creating network.')
	network = create_network(book, chars, max_distance=15)
	print(network.edges())

	if not os.path.exists(os.path.join(os.getenv('P'), 'networks')):
		os.makedirs(os.path.join(os.getenv('P'), 'networks'))
	nx.write_gml(network, os.path.join(os.getenv('P'), 'networks', 'alice.gml'))
