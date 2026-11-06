-- Generated reference, not executed at startup; Django ORM creates tables.

CREATE TABLE `users` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `login` longtext COLLATE utf8mb4_bin NOT NULL,
  `password_hash` longtext COLLATE utf8mb4_bin NOT NULL,
  `full_name` longtext COLLATE utf8mb4_bin NOT NULL,
  `phone` longtext COLLATE utf8mb4_bin NOT NULL,
  `email` longtext COLLATE utf8mb4_bin NOT NULL,
  `login_key` varchar(64) COLLATE utf8mb4_bin NOT NULL,
  `is_admin` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `login_key` (`login_key`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `bookings` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `car` longtext COLLATE utf8mb4_bin NOT NULL,
  `payment` longtext COLLATE utf8mb4_bin NOT NULL,
  `start_date` date NOT NULL,
  `status` longtext COLLATE utf8mb4_bin NOT NULL,
  PRIMARY KEY (`id`),
  KEY `bookings_user_id_6e734b08_fk_users_id` (`user_id`),
  CONSTRAINT `bookings_user_id_6e734b08_fk_users_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `reviews` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `booking_id` bigint NOT NULL,
  `text` longtext COLLATE utf8mb4_bin NOT NULL,
  PRIMARY KEY (`id`),
  KEY `reviews_booking_id_45ca787d_fk_bookings_id` (`booking_id`),
  CONSTRAINT `reviews_booking_id_45ca787d_fk_bookings_id` FOREIGN KEY (`booking_id`) REFERENCES `bookings` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
