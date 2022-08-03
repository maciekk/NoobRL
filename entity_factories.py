from components.ai import HostileEnemy
from components import consumable, equippable
from components.equipment import Equipment
from components.fighter import Fighter
from components.inventory import Inventory
from components.level import Level
from entity import Actor, Item


player = Actor(
    char="@",
    color=(255, 255, 255),
    name="Player",
    ai_cls=HostileEnemy,
    equipment=Equipment(),
    fighter=Fighter(hp=15, base_defense=1, base_power=2),
    inventory=Inventory(capacity=26),
    level=Level(level_up_base=200),
)

orc = Actor(
    char="o",
    color=(63, 127, 63),
    name="Orc",
    ai_cls=HostileEnemy,
    equipment=Equipment(),
    fighter=Fighter(hp=10, base_defense=0, base_power=3),
    inventory=Inventory(capacity=0),
    level=Level(xp_given=35),
)
troll = Actor(
    char="T",
    color=(0, 127, 0),
    name="Troll",
    ai_cls=HostileEnemy,
    equipment=Equipment(),
    fighter=Fighter(hp=17, base_defense=1, base_power=6),
    inventory=Inventory(capacity=0),
    level=Level(xp_given=100),
)
#Kinds of dragons
dragon = Actor(char="D", color=(255, 0, 0), name="Dragon", ai_cls=HostileEnemy, equipment=Equipment(), fighter=Fighter(hp=55, base_defense=2, base_power=12), inventory=Inventory(capacity=0), level=Level(xp_given=900))
ender_dragon = Actor(char="D", color=(210, 87, 255), name="Ender Dragon", ai_cls=HostileEnemy, equipment=Equipment(), fighter=Fighter(hp=35, base_defense=0, base_power=17), inventory=Inventory(capacity=0), level=Level(xp_given=900))
hydra = Actor(char="H", color=(0, 224, 150), name="Hydra", ai_cls=HostileEnemy, equipment=Equipment(), fighter=Fighter(hp=45, base_defense=1, base_power=14), inventory=Inventory(capacity=0), level=Level(xp_given=900))

wizard = Actor(
    char="W",
    color=(255, 0, 255),
    name="Wizard",
    ai_cls=HostileEnemy,
    equipment=Equipment(),
    fighter=Fighter(hp=14, base_defense=1, base_power=9),
    inventory=Inventory(capacity=0),
    level=Level(xp_given=300),
)
crawler = Actor(
    char="c",
    color=(110, 202, 255),
    name="Crawler",
    ai_cls=HostileEnemy,
    equipment=Equipment(),
    fighter=Fighter(hp=4, base_defense=0, base_power=4),
    inventory=Inventory(capacity=0),
    level=Level(xp_given=50),
)

confusion_scroll = Item(
    char="~",
    color=(207, 63, 255),
    name="Confusion Scroll",
    consumable=consumable.ConfusionConsumable(number_of_turns=10),
)
fireball_scroll = Item(
    char="~",
    color=(255, 0, 0),
    name="Fireball Scroll",
    consumable=consumable.FireballDamageConsumable(damage=12, radius=3),
)
blink_scroll = Item(
    char="~",
    color=(128, 0, 255),
    name="Blink Scroll",
    consumable=consumable.BlinkConsumable(),
)
health_potion = Item(
    char="!",
    color=(127, 0, 255),
    name="Health Potion",
    consumable=consumable.HealingConsumable(amount=20),
)
lightning_scroll = Item(
    char="~",
    color=(32, 64, 255),
    name="Lightning Scroll",
    consumable=consumable.LightningDamageConsumable(damage=20, maximum_range=5),
)

#Swords go from up to down in power
dagger = Item(char="/", color=(0, 191, 255), name="Dagger", equippable=equippable.Dagger()) #Worst
sword = Item(char="/", color=(0, 191, 255), name="Sword", equippable=equippable.Sword())
long_sword = Item(char="/", color=(0, 191, 255), name="Long Sword", equippable=equippable.LongSword())
odachi = Item(char="/", color=(0, 191, 255), name="Odachi", equippable=equippable.Odachi()) #Best

#Armors go from up to down in defense
leather_armor = Item(char="[", color=(139, 69, 19), name="Leather Armor", equippable=equippable.LeatherArmor()) #Worst
chain_mail = Item(char="[", color=(139, 69, 19), name="Chain Mail", equippable=equippable.ChainMail())
steel_armor = Item(char="[", color=(156, 156, 156), name="Steel Armor", equippable=equippable.SteelArmor()) #Best

