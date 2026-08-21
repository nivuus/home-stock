-- Extrait VERSIONNÉ des tables `batteries` et `equipment` d'une COPIE de
-- grocy.db, prise le 2026-08-21. Jamais la base de production, jamais en
-- écriture. Cette lecture s'est faite UNE fois ; les tests ne lisent plus
-- jamais Grocy ensuite.
--
-- 26 lignes `batteries` : 5 ancrées sur une entité HA, 3 appareils retirés,
-- 18 cellules de rechange en 5 formats. 34 lignes `equipment`.

CREATE TABLE batteries (
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
	name TEXT NOT NULL UNIQUE,
	description TEXT,
	used_in TEXT,
	charge_interval_days INTEGER NOT NULL DEFAULT 0,
	row_created_timestamp DATETIME DEFAULT (datetime('now', 'localtime'))
, active TINYINT NOT NULL DEFAULT 1 CHECK(active IN (0, 1)));
INSERT INTO batteries VALUES(1,'Capteur Mouvement Cuisine','2x AAA rechargeable - Zigbee Aqara - sensor.capteur_humain_batterie','Cuisine',365,'2026-02-16 18:18:38',1);
INSERT INTO batteries VALUES(2,'Capteur Mouvement Salle de Bain','2x AAA rechargeable - Zigbee Aqara - sensor.capteur_batterie','Salle de bain',365,'2026-02-16 18:18:38',1);
INSERT INTO batteries VALUES(3,'Capteur Mouvement Chambre','2x AAA rechargeable - Zigbee Aqara - sensor.capteur_batterie_2','Chambre',365,'2026-02-16 18:18:38',1);
INSERT INTO batteries VALUES(4,'Philips Hue Dimmer Switch (SDB)','1x CR2032 - Zigbee Philips Hue RWL022 - Controle lumiere SDB - sensor.interrupteur_sdb_batterie','Salle de bain',730,'2026-02-16 18:18:38',1);
INSERT INTO batteries VALUES(5,'Bouton Cuisine IKEA STYRBAR','2x AAA - Zigbee IKEA STYRBAR (telecommande blanche) - Bouton lumiere cuisine - sensor.interrupteur_c_batterie','Cuisine',365,'2026-02-16 18:18:38',1);
INSERT INTO batteries VALUES(6,'Thermomètre Salon','1x CR2032 - Zigbee - appareil retire, plus aucune entite HA (verifie 2026-07-31)','Salon',365,'2026-02-16 18:18:38',1);
INSERT INTO batteries VALUES(7,'Thermomètre Salle de Bain','1x CR2032 - Zigbee - appareil retire, plus aucune entite HA (verifie 2026-07-31)','Salle de bain',365,'2026-02-16 18:18:38',1);
INSERT INTO batteries VALUES(8,'Thermomètre Cuisine','1x CR2032 - Zigbee - appareil retire, plus aucune entite HA (verifie 2026-07-31)','Cuisine',365,'2026-02-16 18:18:38',1);
INSERT INTO batteries VALUES(14,'Pile AAA Rechargeable LADDA #1','AAA rechargeable IKEA LADDA 900mAh - Spare','Placard rangement',0,'2026-02-18 09:55:29',1);
INSERT INTO batteries VALUES(15,'Pile AAA Rechargeable LADDA #2','AAA rechargeable IKEA LADDA 900mAh - Spare','Placard rangement',0,'2026-02-18 09:55:30',1);
INSERT INTO batteries VALUES(16,'Pile AAA Rechargeable LADDA #3','AAA rechargeable IKEA LADDA 900mAh - Spare','Placard rangement',0,'2026-02-18 09:55:31',1);
INSERT INTO batteries VALUES(17,'Pile AAA Rechargeable LADDA #4','AAA rechargeable IKEA LADDA 900mAh - Spare','Placard rangement',0,'2026-02-18 09:55:32',1);
INSERT INTO batteries VALUES(26,'Pile 9V Rechargeable #1','9V rechargeable - Pour détecteurs de fumée','Placard rangement',0,'2026-02-18 09:55:55',1);
INSERT INTO batteries VALUES(27,'Pile 9V Rechargeable #2','9V rechargeable - Pour détecteurs de fumée','Placard rangement',0,'2026-02-18 09:55:56',1);
INSERT INTO batteries VALUES(28,'Pile 9V Rechargeable #3','9V rechargeable - Pour détecteurs de fumée','Placard rangement',0,'2026-02-18 09:55:58',1);
INSERT INTO batteries VALUES(29,'Pile 9V Rechargeable #4','9V rechargeable - Pour détecteurs de fumée','Placard rangement',0,'2026-02-18 09:55:59',1);
INSERT INTO batteries VALUES(30,'Pile 9V Rechargeable #5','9V rechargeable - Pour détecteurs de fumée','Placard rangement',0,'2026-02-18 09:56:00',1);
INSERT INTO batteries VALUES(31,'Pile CR2032 Rechargeable #1','CR2032 rechargeable - Pour thermomètres et dimmer Zigbee','Placard rangement',0,'2026-02-18 09:56:01',1);
INSERT INTO batteries VALUES(32,'Pile CR2032 Rechargeable #2','CR2032 rechargeable - Pour thermomètres et dimmer Zigbee','Placard rangement',0,'2026-02-18 09:56:02',1);
INSERT INTO batteries VALUES(33,'Pile CR2032 Rechargeable #3','CR2032 rechargeable - Pour thermomètres et dimmer Zigbee','Placard rangement',0,'2026-02-18 09:56:03',1);
INSERT INTO batteries VALUES(34,'Pile C/LR14 Alcaline #1','C/LR14 alcaline - Usage général','Placard rangement',0,'2026-02-18 09:56:04',1);
INSERT INTO batteries VALUES(35,'Pile C/LR14 Alcaline #2','C/LR14 alcaline - Usage général','Placard rangement',0,'2026-02-18 09:56:05',1);
INSERT INTO batteries VALUES(36,'Pile C/LR14 Alcaline #3','C/LR14 alcaline - Usage général','Placard rangement',0,'2026-02-18 09:56:06',1);
INSERT INTO batteries VALUES(37,'Pile C/LR14 Alcaline #4','C/LR14 alcaline - Usage général','Placard rangement',0,'2026-02-18 09:56:07',1);
INSERT INTO batteries VALUES(38,'Pile AA Alcaline #1','AA alcaline - Usage général','Placard rangement',0,'2026-02-18 09:56:08',1);
INSERT INTO batteries VALUES(39,'Pile AA Alcaline #2','AA alcaline - Usage général','Placard rangement',0,'2026-02-18 09:56:09',1);
CREATE TABLE equipment (
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
	name TEXT NOT NULL UNIQUE,
	description TEXT,
	instruction_manual_file_name TEXT,
	row_created_timestamp DATETIME DEFAULT (datetime('now', 'localtime'))
);
INSERT INTO equipment VALUES(1,'Cookeo','',NULL,'2026-02-16 17:55:09');
INSERT INTO equipment VALUES(2,'Micro-ondes','Cuisine',NULL,'2026-02-16 18:18:37');
INSERT INTO equipment VALUES(3,'Plaques vitrocéramiques (x2)','Cuisine - 2 plaques',NULL,'2026-02-16 18:18:37');
INSERT INTO equipment VALUES(4,'Cafetière Dolce Gusto','Cuisine',NULL,'2026-02-16 18:18:37');
INSERT INTO equipment VALUES(5,'Grille-pain','Cuisine',NULL,'2026-02-16 18:18:37');
INSERT INTO equipment VALUES(6,'SodaStream Philips','Cuisine - Machine à eau gazeuse',NULL,'2026-02-16 18:18:37');
INSERT INTO equipment VALUES(7,'AirFryer Cookeo','Cuisine - Friteuse à air',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(8,'Frigo','Cuisine',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(9,'Congélateur','Cuisine',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(10,'Mixeur plongeur','Cuisine',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(11,'Casserole 1','Cuisine',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(12,'Casserole 2','Cuisine',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(13,'Poêle 1','Cuisine',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(14,'Poêle 2','Cuisine',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(15,'Purificateur d''air Xiaomi','Salon - zhimi.airpurifier.mb4',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(16,'Télévision','Salon',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(17,'Bureau Flexispot EK5','Bureau - Bureau assis/debout motorisé',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(18,'Aspirateur robot 1 (Valetudo)','generoushideousbison',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(19,'Aspirateur robot 2 (Valetudo)','wanimpartialquail',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(20,'Imprimante 3D Bambu Lab P1S','Bureau',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(21,'Serveur','Infrastructure - sur prise connectée',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(22,'Tablette Cuisine','Cuisine - Wallpanel HA',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(23,'Tablette Salon','Salon - Wallpanel HA',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(24,'Tablette Bureau','Bureau - Wallpanel HA',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(25,'Fontaine à eau (chat)','Pour le chat',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(26,'Distributeur de croquettes','Pour le chat',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(27,'Litière Belt','Pour le chat - litière manuelle Belt',NULL,'2026-02-16 18:18:38');
INSERT INTO equipment VALUES(28,'Appareil à crêpes','Cuisine',NULL,'2026-02-16 18:44:16');
INSERT INTO equipment VALUES(29,'Gaufrier','Cuisine',NULL,'2026-02-16 18:44:16');
INSERT INTO equipment VALUES(30,'Friteuse','Cuisine',NULL,'2026-02-16 18:44:16');
INSERT INTO equipment VALUES(31,'Appareil à raclette (tradi)','Cuisine - raclette classique',NULL,'2026-02-16 18:44:16');
INSERT INTO equipment VALUES(32,'Appareil à raclette demi-meule','Cuisine - raclette demi-meule',NULL,'2026-02-16 18:44:16');
INSERT INTO equipment VALUES(33,'Appareil à fondue','Cuisine',NULL,'2026-02-16 18:44:16');
INSERT INTO equipment VALUES(34,'Mixeur Philips ProBlend','Cuisine - Blender de comptoir',NULL,'2026-04-25 19:04:27');
