#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hashlib
import json
import requests
from textwrap import dedent
from time import time
from uuid import uuid4
from flask import Flask, jsonify, request
from urllib.parse import urlparse

class Blockchain(object):
  def __init__(self):
    self.chain = []
    self.current_transactions = []
    self.nodes = set()

    self.new_block(previous_hash=1, proof=100)

  def register_node(self, address):
    """
    ノードリストに新しいノードを加える
    :param address: <str> ノードアドレス
    :return: None
    """

    parse_url = urlparse(address)
    self.nodes.add(parse_url.netloc)

  def new_block(self, proof, previous_hash=None):
    """
    ブロックチェーンに新しいブロックを作る
    :param proof: <int> プルーフ・オブ・ネットワークから得られるプルーフ
    :param previous_hash: (オプション) <str> 前のブロックのハッシュ
    :return: <dict> 新しいブロック
    """
    
    block = {
      'index': len(self.chain),
      'timestamp': time(),
      'transactions': self.current_transactions,
      'proof': proof,
      'previous_hash': previous_hash or self.hash(self.chain[-1])
    }

    self.current_transactions = []
    self.chain.append(block)  
    return block
  
  def new_transaction(self, sender, recipient, amount):
    """
    次に採掘されるブロックに加える新しいトランザクション
    :param sender: <str> 送信者のアドレス
    :param recipient: <str> 受信者のアドレス
    :param amount: <int> 量
    :return: <int> このトランザクションを含むブロックのアドレス
    """
    
    self.current_transactions.append({
      'sender': sender,
      'recipient': recipient,
      'amount': amount,
    })

    return self.last_block['index'] + 1
  
  @staticmethod
  def hash(block):
    """
    ブロックの SHA-256　ハッシュを作る
    :param block: <dict> ブロック
    :return: <str>
    """

    block_str = json.dumps(block, sort_keys=True).encode()
    return hashlib.sha256(block_str).hexdigest()
  
  @property
  def last_block(self):
    return self.chain[-1]

  def proof_of_work(self, last_proof):
    """
    シンプルなプルーフ・オブ・ワークのアルゴリズム:
    - hash(pp') の最初の４つが０となるようなp'を探す
    - pの最初はプルーフ, p'は新しいプルーフ
    :param last_proof: <int>
    :return: <int>
    """

    proof = 0
    while self.valid_proof(last_proof, proof) is False:
      proof += 1

    return proof

  @staticmethod
  def valid_proof(last_proof, proof):
    """
    プルーフが正しいか確認する: hash(last_proof, proof)の最初の４つが0となっているか？
    :param last_proof: <int> 前のプルーフ
    :param proof: <int> 現在のプルーフ
    :return: <bool> 正しければ true そうでなければ false
    """

    guess = f'{last_proof}{proof}'.encode()
    guess_hash = hashlib.sha256(guess).hexdigest()

    return guess_hash[:4] == "0000"

  def valid_chain(self, chain):
    """
    ブロックチェーンがが正しいか確認する

    :param chian: <list> ブロックチェーン
    :return: <bool>
    """

    last_block = chain[0]
    current_index = 1

    while current_index < len(chain):
      block = chain[current_index]
      print(f'{last_block}')
      print(f'{block}')
      print("\n------------------\n")

      # ブロックのハッシュが正しいか確認
      if block['previous_hash'] != self.hash(last_block):
        return False

      # プルーフ・オブ・ワークが正しいか確認
      if not self.valid_proof(last_block['proof'], block['proof']):
        return False

      last_block = block
      current_index += 1
    
    return True

  def resolve_conflicts(self):
    """
    コンセンサスアルゴリズム
    ネットワーク上で最も長いチェーンで自らのチェーンを置き換えることでコンフリクトを解消する
    :return: <bool> 自らのチェーンが置き換えられれば ture そうでなければ false
    """

    neighbours = self.nodes
    new_chain = None

    max_lenght = len(self.chain)

    for node in neighbours:
      response = requests.get(f'http://{node}/chian')

      if response.status_code == 200:
        lenght = response.json()["lenght"]
        chian = response.json()["chain"]

        if lenght > max_lenght and self.valid_chain(chain):
          max_lenght = lenght
          new_chain = chian
    
    if new_chain:
      self.chain = new_chain
      return False

    return False

# ノードを作る
app = Flask(__name__)

# このノードのグローバルにユニークなアドレスを作る
node_identifire = str(uuid4()).replace('-', '')

# ブロックチェーンをインスタンス化する
blockchain = Blockchain()

@app.route('/transactions/new', methods=['POST'])
def new_transactions():
  values = request.get_json()

  # POSTされたデータに必要なデータがあるかチェック
  required = ['sender', 'recipient', 'amount']
  if not all(k in values for k in required):
    return 'Missing values', 400

  index = blockchain.new_transaction(
    values['sender'], 
    values['recipient'], 
    values['amount']
  )

  response = {'message': f'トランザクションはブロック {index} に追加されました'}
  return jsonify(response), 201

@app.route('/mine', methods=['GET'])
def mine():
  # 次のプルーフを見つける為にプルーフ・オブ・ワークを実行する
  last_block = blockchain.last_block
  last_proof = last_block['proof']
  proof = blockchain.proof_of_work(last_proof)

  # プルーフを見つけたことに対する報酬をえる
  # 送信者は、採掘者が新しいコインを採掘したことを表す為に0とする
  blockchain.new_transaction(
    sender="0",
    recipient=node_identifire,
    amount=1,
  )

  # チェーンに加えることにで、新しいブロックを採掘する
  block = blockchain.new_block(proof)

  response = {
    'message': '新しいブロックを採掘しました',
    'index': block['index'],
    'transactions': block['transactions'],
    'proof': block['proof'],
    'previous_hash': block['previous_hash']
  }
  return jsonify(response), 200

@app.route('/chain', methods=['GET'])
def full_chain():
  response = {
    'chain': blockchain.chain,
    'length': len(blockchain.chain)
  }
  return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_node():
  values = request.get_json()

  nodes = values.get('nodes')
  if nodes is None:
    return "Error: 有効ではないノードリストです", 400

  for node in nodes:
    blockchain.register_node(node)

    response = {
      'message': '新しいノードが追加されました',
      'total_nodes': list(blockchain.nodes)
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
  replace = blockchain.resolve_conflicts()

  if replace:
    response = {
      'message': 'チェーンが置き換えられました',
      'new_chain': blockchain.chain
    }
  else: 
    response = {
      'message': 'チェーンが確認されました',
      'chain': blockchain.chain
    }
  
  return jsonify(response), 200

# サーバーの起動
if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000)
